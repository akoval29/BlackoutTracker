"""Persistent schedule-change detection and bounded event history."""
import json
from copy import deepcopy
from blackout_tracker.storage import save_json_atomic
from blackout_tracker.regions import REGIONS


class EventJournal:
    def __init__(self, path):
        self.path = path
        self.events = []
        self.snapshots = {}
        self.error = ''
        try:
            stored = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(stored.get('events'), list) and isinstance(stored.get('snapshots'), dict):
                self.events = stored['events'][-500:]
                self.snapshots = stored['snapshots']
        except (OSError, ValueError, AttributeError):
            pass

    def clear(self):
        """Clear history while preserving the baseline for future changes."""
        try:
            save_json_atomic(self.path, {'events': [], 'snapshots': self.snapshots})
        except OSError:
            self.error = 'Не вдалося очистити журнал на диску. Події збережено.'
            return False
        self.events = []
        self.error = ''
        return True

    def observe(self, schedule, now, previous=None):
        key = schedule['region'] + '/' + schedule['group']
        baseline = self.snapshots.get(key)
        if baseline is None and previous and (previous.get('region'), previous.get('group')) == (schedule['region'], schedule['group']):
            baseline = previous.get('days', [])
        today = now.date().isoformat()
        old_days = {d['date']: d for d in (baseline or [])}
        events = []
        for day in sorted(schedule['days'], key=lambda d: d['date']):
            if day['date'] < today or day['status'] == 'unknown':
                continue
            old = old_days.get(day['date'])
            if day['status'] == 'emergency':
                title = 'Екстрені відключення' if not old or old['status'] != 'emergency' else None
            elif old and old['status'] == 'emergency':
                title = 'Повернення до планового графіка'
            elif baseline is not None and (not old or old['status'] == 'unknown'):
                title = 'Опубліковано графік'
            elif old and (old['status'], old.get('intervals', [])) != (day['status'], day.get('intervals', [])):
                title = 'Змінено графік'
            else:
                title = None
            if title:
                events.append({'time': now.isoformat(), 'title': title, 'region': schedule['region'],
                               'group': schedule['group'], 'date': day['date'],
                               'before': deepcopy(old), 'after': deepcopy(day)})
        self.snapshots[key] = deepcopy(schedule['days'])
        self.events = (self.events + events)[-500:]
        try:
            save_json_atomic(self.path, {'events': self.events, 'snapshots': self.snapshots})
            self.error = ''
        except OSError:
            self.error = 'Не вдалося зберегти журнал на диск. Події доступні в цьому сеансі.'
        return events


def event_summary(event):
    region = REGIONS.get(event['region'], event['region'])
    date = '.'.join(reversed(event['date'].split('-')))
    return f"{region} · Черга {event['group']} · {date}"


def describe_day(day):
    if not day or day['status'] == 'unknown':
        return 'Графік не опублікований'
    if day['status'] == 'emergency':
        return 'Екстрені відключення — план не діє'
    from blackout_tracker.schedule import format_time
    intervals = day.get('intervals', [])
    return '; '.join(f"{format_time(start)}–{format_time(end)}" + (' (можливе)' if kind == 'maybe' else '')
                     for start, end, kind in intervals) or 'Без планових відключень'
