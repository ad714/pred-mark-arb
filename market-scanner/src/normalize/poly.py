from src.normalize.utils import parse_utc
import re

from datetime import datetime, timezone

def is_active_market(m):
    if not m.get("accepting_orders"):
        return False
    if not m.get("active"):
        return False
    if m.get("closed"):
        return False

    t = m.get("game_start_time") or m.get("end_date_iso")
    if not t:
        return False

    market_time = datetime.fromisoformat(t.replace("Z", "+00:00"))
    return market_time > datetime.now(timezone.utc)


def extract_participants(question: str, tokens: list):
    # Prefer tokens, they are explicit
    if tokens and len(tokens) == 2:
        return tokens[0]["outcome"], tokens[1]["outcome"]

    # Fallback: parse from question
    # Example: "NCAAB: Arizona State Sun Devils vs. Nevada Wolf Pack 2023-03-15"
    if " vs. " in question:
        left, right = question.split(" vs. ", 1)
        home = left.split(":")[-1].strip()
        away = right.split(" 20")[0].strip()
        return home, away

    return None, None


def normalize_poly_market(raw: dict):
    question = raw.get("question", "")
    tokens = raw.get("tokens", [])

    home, away = extract_participants(question, tokens)
    if not home or not away:
        return None

    start_time = raw.get("game_start_time") or raw.get("end_date_iso")

    return {
        "platform": "polymarket",
        "platform_market_id": raw.get("condition_id"),
        "sport": "basketball",   # derived from NCAAB
        "competition": "NCAAB",
        "event": {
            "home": home,
            "away": away,
            "participants": [home, away],
            "start_time_utc": parse_utc(start_time)
        },
        "market_type": "match_winner",
        "market_scope": "regular_time",
        "line": None,
        "outcomes": [
            {"key": "home", "label": home},
            {"key": "away", "label": away}
        ]
    }
