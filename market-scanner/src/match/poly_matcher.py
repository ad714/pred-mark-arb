import re
from datetime import datetime, timezone
from difflib import SequenceMatcher


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_teams(text: str):
    """
    Extract two sides from 'Team A vs Team B' or 'Team A v Team B'
    """
    t = normalize_text(text)

    if " vs " in t:
        return t.split(" vs ", 1)
    if " v " in t:
        return t.split(" v ", 1)

    return None, None


def token_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def team_overlap_score(fliq_title: str, poly_title: str) -> float:
    fa, fb = extract_teams(fliq_title)
    pa, pb = extract_teams(poly_title)

    if not all([fa, fb, pa, pb]):
        return 0.0

    scores = [
        token_similarity(fa, pa),
        token_similarity(fa, pb),
        token_similarity(fb, pa),
        token_similarity(fb, pb),
    ]

    return max(scores)


def date_proximity_score(fliq_end_date: str, poly_start: str) -> float:
    if not fliq_end_date or not poly_start:
        return 0.0

    try:
        fliq_dt = datetime.fromisoformat(fliq_end_date).astimezone(timezone.utc)
        poly_dt = datetime.fromisoformat(poly_start.replace("Z", "+00:00"))
    except Exception:
        return 0.0

    diff_hours = abs((fliq_dt - poly_dt).total_seconds()) / 3600

    if diff_hours <= 6:
        return 1.0
    if diff_hours <= 24:
        return 0.6
    if diff_hours <= 48:
        return 0.3
    return 0.0


def structure_score(text: str) -> float:
    t = text.lower()
    return 1.0 if (" vs " in t or " v " in t) else 0.0


def compute_match_score(fliq_match: dict, poly_event: dict) -> float:
    score = 0.0

    # 1. Structural signal
    score += 0.4 * structure_score(poly_event.get("title", ""))

    # 2. Team overlap
    score += 0.3 * team_overlap_score(
        fliq_match["parent_question"],
        poly_event.get("title", "")
    )

    # 3. Date proximity
    score += 0.2 * date_proximity_score(
        fliq_match["end_date"],
        poly_event.get("startDate")
    )

    # 4. Competition hint
    comp = fliq_match["parent_question"].lower()
    poly_comp = (poly_event.get("tags") or [])
    if any(tag.get("label", "").lower() in comp for tag in poly_comp):
        score += 0.1

    return round(min(score, 1.0), 3)


def classify_match(score):
    if score >= 0.7:
        return "matched"
    if score >= 0.35:
        return "review"
    return "no_match"

