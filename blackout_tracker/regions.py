DEFAULT_REGION = 'kyiv-region'
REGIONS = {
    'kyiv-region': 'Київська область',
    'kyiv': 'м. Київ',
    'odesa': 'Одеська область',
    'dnipro': 'Дніпропетровська область',
}
GROUPS = [f'{a}.{b}' for a in range(1, 7) for b in (1, 2)]


def groups_for(region):
    return [f'{a}.1' for a in range(1, 61)] if region == 'kyiv' else list(GROUPS)


def valid_group(region, group):
    return group if group in groups_for(region) else groups_for(region)[0]
