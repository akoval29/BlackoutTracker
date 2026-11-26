"""Validated schedule adapters. All dates and boundaries use Europe/Kyiv."""
import json
import re
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from blackout_tracker.regions import DEFAULT_REGION, REGIONS, groups_for

KYIV_TIMEZONE = ZoneInfo('Europe/Kyiv')
SCHEDULE_URL = 'https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/kyiv-region.json'


def read_json(url):
    request = Request(url, headers={'User-Agent': 'BlackoutTracker/0.12', 'Accept': 'application/json'})
    with urlopen(request, timeout=15) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Завелика відповідь сервера')
        return json.loads(body)


def parse_timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Час джерела не має часового поясу')
    return result


def parse_schedule_response(data, group, region=DEFAULT_REGION):
    if region not in REGIONS or group not in groups_for(region) or data['regionId'] != region or data['lastUpdateStatus']['ok'] is not True:
        raise ValueError('Не вдалося підтвердити актуальність графіка')
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
                raise ValueError('Невідомий стан у графіку')
            for start, end, state in ranges[kind]:
                start, end = start + (hour - 1) * 60, end + (hour - 1) * 60
                if intervals and intervals[-1][1] == start and intervals[-1][2] == state:
                    intervals[-1][1] = end
                else:
                    intervals.append([start, end, state])
        days.append({'date': datetime.fromtimestamp(int(epoch), KYIV_TIMEZONE).date().isoformat(),
                     'status': 'scheduled' if intervals else 'no-outages', 'intervals': intervals})
    checked = data['lastUpdateStatus']['at']
    parse_timestamp(checked)
    updated = datetime.strptime(data['fact']['update'], '%d.%m.%Y %H:%M').replace(tzinfo=KYIV_TIMEZONE)
    attention = (data.get('attention') or {}).get('text', '').lower()
    emergency = bool(re.search(r'(?<!не )\b(?:впровадж\w*|застос\w*|діють|введен\w*)\s+(?:екстрен\w*|аварійн\w*)\s+відключ', attention))
    if emergency:
        checked_date = parse_timestamp(checked).astimezone(KYIV_TIMEZONE).date().isoformat()
        for day in days:
            if day['date'] == checked_date:
                day['status'] = 'emergency'
    warning = 'У регіоні повідомлено про екстрені відключення. План може не діяти.' if emergency else ''
    return {'region': region, 'group': group, 'warning': warning, 'provider': 'github', 'checked': checked,
            'updated': updated.isoformat(), 'stale': False, 'days': days}


def is_schedule_fresh(schedule, now):
    age = (now - parse_timestamp(schedule['checked'])).total_seconds()
    return not schedule['stale'] and -300 <= age <= 1800


def fetch_schedule(group, region=DEFAULT_REGION):
    if region not in REGIONS or group not in groups_for(region):
        raise ValueError('Невідома черга')
    try:
        url = SCHEDULE_URL.replace('/kyiv-region.json', f'/{region}.json')
        result = parse_schedule_response(read_json(url), group, region)
        now = datetime.now(KYIV_TIMEZONE)
        if not is_schedule_fresh(result, now) or not any(d['date'] == now.date().isoformat() for d in result['days']):
            raise ValueError('Немає актуального графіка на сьогодні')
        return result
    except Exception:
        # Keep transport URLs and provider names out of user-visible errors.
        raise ValueError('Не вдалося отримати актуальний графік. Перевірте підключення та спробуйте пізніше.') from None


def format_time(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'



def outage_color(seconds):
    # Continuous green-to-red countdown, clamped at 60 and 10 minutes.
    progress = max(0.0, min(1.0, (3600 - seconds) / 3000))
    green, red = (94, 224, 175), (248, 113, 113)
    channels = [round(a + (b - a) * progress) for a, b in zip(green, red)]
    return '#' + ''.join(f'{channel:02x}' for channel in channels)


def get_schedule_state(schedule, now):
    """Return label, next known boundary and countdown color. Never infer unknown days."""
    if not schedule:
        return 'Очікуємо графік', None, '#8190a8'
    daymap = {d['date']: d for d in schedule['days']}
    current = daymap.get(now.date().isoformat())
    if not current or current['status'] == 'unknown':
        return 'Графік ще не опубліковано', None, '#8190a8'
    if current['status'] == 'emergency':
        return 'Екстрені відключення — графік не діє', None, '#f6ad55'
    midnight = datetime.combine(now.date(), datetime.min.time(), KYIV_TIMEZONE)
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
            return label, midnight + timedelta(minutes=start), outage_color((start - minute) * 60)
    tomorrow = daymap.get((now.date() + timedelta(days=1)).isoformat())
    if tomorrow and tomorrow['status'] == 'scheduled' and tomorrow['intervals']:
        start, _, kind = tomorrow['intervals'][0]
        return ('До можливого відключення' if kind == 'maybe' else 'До відключення за графіком',
                midnight + timedelta(days=1, minutes=start),
                outage_color((midnight + timedelta(days=1, minutes=start) - now).total_seconds()))
    return 'У відомому графіку більше немає відключень', None, '#5ee0af'
