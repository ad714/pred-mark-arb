from datetime import datetime
from collections import defaultdict

def normalize_all_fliq_events(questions: list):
    """
    Groups template-based match questions into single match events
    """
    grouped = defaultdict(list)

    for q in questions:
        meta = q.get("blockchainMetadata", {})

        # STRICT FILTERS
        if not meta.get("isMadeByTemplate"):
            continue

        parent_id = meta.get("parentQuestionId")
        parent_header = meta.get("parentQuestionHeader")

        if not parent_id or not parent_header:
            continue

        if " vs " not in parent_header.lower():
            continue

        grouped[parent_id].append(q)

    events = []
    for group in grouped.values():
        norm = normalize_fliq_event(group)
        if norm:
            events.append(norm)

    return events


def normalize_fliq_event(questions: list):
    meta = questions[0]["blockchainMetadata"]
    parent = meta["parentQuestionHeader"]

    # Example:
    # Match Result: Villarreal vs Barcelona, 21st Dec, La Liga
    try:
        core = parent.replace("Match Result:", "").strip()
        teams_part, rest = core.split(",", 1)
        home, away = teams_part.split(" vs ")
    except Exception:
        return None

    home = home.strip()
    away = away.strip()

    ts = meta.get("questionEndTime")
    start_time = (
        datetime.utcfromtimestamp(ts).isoformat() if ts else None
    )

    outcomes = {}

    for q in questions:
        header = q["blockchainMetadata"].get("questionHeader", "").lower()
        qid = q.get("questionId")

        if "draw" in header:
            outcomes["draw"] = {"market_id": qid}
        elif home.lower() in header:
            outcomes["home"] = {"market_id": qid}
        elif away.lower() in header:
            outcomes["away"] = {"market_id": qid}

    if len(outcomes) < 2:
        return None

    return {
        "platform": "fliq",
        "event_id": meta["parentQuestionId"],
        "sport": meta.get("category"),
        "competition": rest.strip(),
        "event": {
            "home": home,
            "away": away,
            "participants": [home, away],
            "start_time_utc": start_time
        },
        "market_type": "match_winner",
        "outcomes": outcomes
    }
