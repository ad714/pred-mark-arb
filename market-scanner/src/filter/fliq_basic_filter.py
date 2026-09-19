import re

BAD_KEYWORDS = [
    "kill", "custom", "room", "pubg", "free fire",
    "rush hour", "bangladesh", "jon", "coustom"
]

def is_probable_match(question: str) -> bool:
    if not question:
        return False

    q = question.lower()

    # must look like a match
    if not re.search(r"\bvs\b|\bv\b|\bvs\.\b", q):
        return False

    # reject obvious junk
    for bad in BAD_KEYWORDS:
        if bad in q:
            return False

    return True
