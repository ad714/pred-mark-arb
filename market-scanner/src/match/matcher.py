def norm_team(name: str):
    return (
        name.lower()
        .replace('fc ', '')
        .replace(' cf', '')
        .replace('fc', '')
        .replace('cf', '')
        .strip()
    )

def same_event(a: dict, b: dict):
    if a['sport'] != b['sport']:
        return False

    if a['competition'].lower() != b['competition'].lower():
        return False

    a_home = norm_team(a['event']['home'])
    a_away = norm_team(a['event']['away'])

    b_home = norm_team(b['event']['home'])
    b_away = norm_team(b['event']['away'])

    return {a_home, a_away} == {b_home, b_away}