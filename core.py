"""Validated schedule adapters. All dates and boundaries use Europe/Kyiv."""
import json
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

KYIV = ZoneInfo('Europe/Kyiv')
GROUPS = [f'{a}.{b}' for a in range(1, 7) for b in (1, 2)]
PRIMARY = 'https://gpv-ua.com/api/v1/regions/kyiv-region/groups/{}'
BACKUP = 'https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/kyiv-region.json'


def read_json(url):
    request = Request(url, headers={'User-Agent': 'BlackoutTracker/0.2', 'Accept': 'application/json'})
    with urlopen(request, timeout=15) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Завелика відповідь сервера')
        return json.loads(body)


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Час джерела не має часового поясу')
    return result


def normalize_gpv(data, group):
    if data['region']['slug'] != 'kyiv-region' or data['group'] != group:
        raise ValueError('Джерело повернуло інший регіон або чергу')
    health = data['region']['health']
    checked = health['succeededAt']
    timestamp(checked)
    days = []
    for day in data['days']:
        datetime.strptime(day['date'], '%Y-%m-%d')
        if day['status'] not in ('scheduled', 'unknown', 'emergency', 'no-outages'):
            raise ValueError('Невідомий стан графіка')
        intervals = []
        previous_end = 0
        for start, end, kind in day['intervals']:
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= 1440:
                raise ValueError('Некоректний інтервал')
            if start < previous_end or kind not in ('off', 'maybe'):
                raise ValueError('Некоректний тип або перетин інтервалів')
            intervals.append([start, end, kind])
            previous_end = end
        days.append({'date': day['date'], 'status': day['status'], 'intervals': intervals})
    if len({d['date'] for d in days}) != len(days):
        raise ValueError('Дубльовані дати')
    return {'group': group, 'source': 'GPV-UA', 'checked': checked,
            'updated': health.get('sourceUpdatedAt'), 'stale': health.get('stale', True)
            or health.get('status') != 'ok', 'days': days}


def normalize_github(data, group):
    if data['regionId'] != 'kyiv-region' or data['lastUpdateStatus']['ok'] is not True:
        raise ValueError('Резервне джерело не оновлюється')
    days = []
    for epoch, groups in data['fact']['data'].items():
        slots = groups.get('GPV' + group)
        if slots is None:
            continue
        intervals = []
        for hour in range(1, 25):
            kind = slots[str(hour)]
            ranges = {'yes': [], 'no': [(0, 60, 'off')], 'first': [(0, 30, 'off')],
                      'second': [(30, 60, 'off')], 'maybe': [(0, 60, 'maybe')],
                      'mfirst': [(0, 30, 'maybe')], 'msecond': [(30, 60, 'maybe')]}
            if kind not in ranges:
                raise ValueError('Невідомий стан у резервному графіку')
            for start, end, state in ranges[kind]:
                start, end = start + (hour - 1) * 60, end + (hour - 1) * 60
                if intervals and intervals[-1][1] == start and intervals[-1][2] == state:
                    intervals[-1][1] = end
                else:
                    intervals.append([start, end, state])
        days.append({'date': datetime.fromtimestamp(int(epoch), KYIV).date().isoformat(),
                     'status': 'scheduled' if intervals else 'no-outages', 'intervals': intervals})
    checked = data['lastUpdateStatus']['at']
    timestamp(checked)
    updated = datetime.strptime(data['fact']['update'], '%d.%m.%Y %H:%M').replace(tzinfo=KYIV)
    return {'group': group, 'source': 'GitHub · резерв', 'checked': checked,
            'updated': updated.isoformat(), 'stale': False, 'days': days}


def fresh(schedule, now):
    age = (now - timestamp(schedule['checked'])).total_seconds()
    return not schedule['stale'] and -300 <= age <= 1800


def fetch_schedule(group):
    errors = []
    for url, parser in ((PRIMARY.format(group), normalize_gpv), (BACKUP, normalize_github)):
        try:
            result = parser(read_json(url), group)
            now = datetime.now(KYIV)
            if not fresh(result, now) or not any(d['date'] == now.date().isoformat() for d in result['days']):
                raise ValueError('Джерело не має свіжих даних на сьогодні')
            result['warning'] = 'Основне джерело недоступне; використано резерв.' if errors else ''
            return result
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {exc}')
    raise ValueError('Не вдалося оновити графік. ' + ' / '.join(errors))


def clock_text(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def state_at(schedule, now):
    """Return label, next known boundary and tray color. Never infer unknown days."""
    if not schedule:
        return 'Очікуємо графік', None, '#8190a8'
    daymap = {d['date']: d for d in schedule['days']}
    current = daymap.get(now.date().isoformat())
    if not current or current['status'] == 'unknown':
        return 'Графік ще не опубліковано', None, '#8190a8'
    if current['status'] == 'emergency':
        return 'Екстрені відключення — графік не діє', None, '#f6ad55'
    midnight = datetime.combine(now.date(), datetime.min.time(), KYIV)
    minute = (now.hour * 60 + now.minute) + now.second / 60
    for start, end, kind in current['intervals']:
        if start <= minute < end:
            target = midnight + timedelta(minutes=end)
            if kind == 'maybe':
                return 'Можливе відключення', target, '#f6ad55'
            # Merge consecutive outages across midnight, only if the next day is known.
            while target.hour == 0 and target.minute == 0:
                following = daymap.get(target.date().isoformat())
                if not following or following['status'] not in ('scheduled', 'no-outages'):
                    return 'Відключення за графіком; час відновлення невідомий', None, '#f87171'
                first = next((i for i in following['intervals'] if i[0] == 0), None)
                if first and first[2] == 'off':
                    target += timedelta(minutes=first[1])
                elif first and first[2] == 'maybe':
                    return 'Відключення; далі можливі обмеження', None, '#f6ad55'
                else:
                    break
            return 'До відновлення за графіком', target, '#f87171'
        if start > minute:
            label = 'До можливого відключення' if kind == 'maybe' else 'До відключення за графіком'
            return label, midnight + timedelta(minutes=start), '#f6ad55' if start - minute <= 60 else '#5ee0af'
    tomorrow = daymap.get((now.date() + timedelta(days=1)).isoformat())
    if tomorrow and tomorrow['status'] == 'scheduled' and tomorrow['intervals']:
        start, _, kind = tomorrow['intervals'][0]
        return ('До можливого відключення' if kind == 'maybe' else 'До відключення за графіком',
                midnight + timedelta(days=1, minutes=start), '#5ee0af')
    return 'У відомому графіку більше немає відключень', None, '#5ee0af'
