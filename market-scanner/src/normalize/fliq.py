from src.normalize.utils import parse_utc
from datetime import datetime

def extract_participants(parent_header: str):
    if not parent_header:
        return None, None

    # Example:
    # "Match Result: Trinidad & Tobago vs Jamaica, 14th Nov, World Cup Qualification CONCACAF"
    if " vs " not in parent_header:
        return None, None

    teams_part = parent_header.split("vs")
    home = teams_part[0].split(":")[-1].strip()
    away = teams_part[1].split(",")[0].strip()
    return home, away


def classify_market_type(question_header: str):
    q = question_header.lower()
    if "to win" in q or "match result" in q:
        return "match_winner"
    return "unknown"


def normalize_fliq_market(raw: dict):
    meta = raw.get("blockchainMetadata", {})
    parent = meta.get("parentQuestionHeader", "")
    question = meta.get("questionHeader", "")
    category = meta.get("category", "")

    home, away = extract_participants(parent)
    if not home or not away:
        return None

    market_type = classify_market_type(question)
    if market_type == "unknown":
        return None

    # Convert unix timestamp → ISO
    end_ts = meta.get("questionEndTime")
    start_time = (
        datetime.utcfromtimestamp(end_ts).isoformat()
        if end_ts else None
    )

    return {
        "platform": "fliq",
        "platform_market_id": raw.get("questionId"),
        "sport": category.lower(),
        "competition": parent,
        "event": {
            "home": home,
            "away": away,
            "participants": [home, away],
            "start_time_utc": start_time
        },
        "market_type": market_type,
        "market_scope": "regular_time",
        "line": None,
        "outcomes": [
            {"key": "yes", "label": question},
            {"key": "no", "label": f"Not {question}"}
        ]
    }
