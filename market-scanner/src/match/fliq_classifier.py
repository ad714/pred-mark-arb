import re

def is_match_event(text: str) -> bool:
    if not text:
        return False

    t = text.lower().strip()

    # must contain vs / v
    if " vs " not in t and " v " not in t:
        return False

    # exclude known non-match patterns
    banned_starts = (
        "will ",
        "who will",
        "in which",
        "when will",
        "how many",
    )

    if t.startswith(banned_starts):
        return False

    banned_keywords = (
        "score",
        "attempt",
        "passes",
        "goals",
        "season",
        "win the",
        "be crowned",
        "relegated",
        "golden boot",
        "retire",
        "announce",
        "complete",
        "reach the",
    )

    for kw in banned_keywords:
        if kw in t:
            return False

    # must look like "Team A vs Team B"
    teams = re.split(r"\s+vs\s+|\s+v\s+", t)
    if len(teams) != 2:
        return False

    # each side must have at least one word
    if len(teams[0].split()) == 0 or len(teams[1].split()) == 0:
        return False

    return True
