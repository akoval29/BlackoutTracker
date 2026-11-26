import json
from regions import DEFAULT_REGION, REGIONS, valid_group

DEFAULTS = {'region': DEFAULT_REGION, 'group': '6.1', 'overlay_topmost': True, 'overlay_position': 'top-right', 'refresh_minutes': 2, 'sound_enabled': True, 'sound_name': 'warning'}


def normalize_settings(value, group='6.1'):
    if not isinstance(value, dict):
        value = {}
    result = dict(DEFAULTS, group=group)
    if value.get('region') in REGIONS:
        result['region'] = value['region']
    result['group'] = valid_group(result['region'], group)
    for key in ('overlay_topmost', 'sound_enabled'):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    if value.get('sound_name') in ('warning', 'bell', 'siren'):
        result['sound_name'] = value['sound_name']
    if value.get('overlay_position') in ('top', 'top-right', 'top-left', 'bottom-right', 'bottom-left'):
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
