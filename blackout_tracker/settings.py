"""Defaults and validation for persisted user settings."""
import json
from blackout_tracker.regions import DEFAULT_REGION, REGIONS, valid_group

DEFAULTS = {'region': DEFAULT_REGION, 'group': '6.1', 'overlay_topmost': True, 'overlay_position': 'bottom', 'overlay_enabled': True, 'refresh_minutes': 15, 'notify_5_minutes': True, 'notify_10_minutes': False}


def normalize_settings(value, group='6.1'):
    if not isinstance(value, dict):
        value = {}
    result = dict(DEFAULTS, group=group)
    if value.get('region') in REGIONS:
        result['region'] = value['region']
    result['group'] = valid_group(result['region'], group)
    for key in ('overlay_enabled', 'overlay_topmost', 'notify_5_minutes', 'notify_10_minutes'):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    if 'notify_5_minutes' not in value and type(value.get('sound_enabled')) is bool:
        result['notify_5_minutes'] = value['sound_enabled']
    if value.get('overlay_position') in ('top', 'top-right', 'top-left', 'bottom-right', 'bottom-left', 'bottom'):
        result['overlay_position'] = value['overlay_position']
    interval = value.get('refresh_minutes')
    if type(interval) is int and 1 <= interval <= 30:
        result['refresh_minutes'] = interval
    return result


def load_settings(path, group):
    try:
        return normalize_settings(json.loads(path.read_text(encoding='utf-8')), group)
    except (OSError, ValueError):
        return normalize_settings({}, group)
