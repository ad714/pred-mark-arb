from src.normalize.utils import normalize_name, minutes_diff

def hard_constraints_pass(fliq, poly):
    if fliq["sport"] != poly["sport"]:
        return False

    if fliq["market_type"] != poly["market_type"]:
        return False

    f_participants = set(map(normalize_name, fliq["event"]["participants"]))
    p_participants = set(map(normalize_name, poly["event"]["participants"]))

    if f_participants != p_participants:
        return False

    if minutes_diff(
        fliq["event"]["start_time_utc"],
        poly["event"]["start_time_utc"]
    ) > 15:
        return False

    return True


def compute_score(fliq, poly):
    score = 0

    # Participants match
    score += 40

    # Time proximity
    diff = minutes_diff(
        fliq["event"]["start_time_utc"],
        poly["event"]["start_time_utc"]
    )
    if diff <= 2:
        score += 25
    elif diff <= 5:
        score += 20
    else:
        score += 10

    # Competition match
    if fliq["competition"] and poly["competition"]:
        if normalize_name(fliq["competition"]) == normalize_name(poly["competition"]):
            score += 15

    # Outcome structure
    if len(fliq["outcomes"]) == len(poly["outcomes"]):
        score += 20

    return score
