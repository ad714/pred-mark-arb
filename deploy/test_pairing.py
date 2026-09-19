import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "live-edge"))

import datetime

import paper_trade as pt

NAME_CASES = [
    ("India A Women", "India Under-19s", False),
    ("India A Women", "India A Women", True),
    ("India Women", "India", False),
    ("Australia", "Australia A", False),
    ("Sri Lanka", "Sri Lanka", True),
    ("Pakistan Women", "Sri Lanka Women", False),
    ("Pakistan Women", "Pakistan Women", True),
    ("Hong Kong, China", "Hong Kong", True),
    ("Trent Rockets", "Trent Rockets", True),
    ("Northern Cape", "Northern Districts", False),
    ("England", "England", True),
    ("Guyana Amazon Warriors", "Jamaica Kingsmen", False),
]

DATE_CASES = [
    ("crint-pakw-lkaw-2026-09-19", "2026-09-20", True),
    ("crint-bgdw-indw-2026-09-20", "2026-09-20", True),
    ("crint-gbr-lka-2026-09-24", "2026-09-19", False),
    ("crint-gbr-lka-2026-09-19", "2026-09-19", True),
    ("crint-zwe-aus-2026-09-20", "2026-09-20", True),
    ("crint-zwe-aus-2026-09-20", "2026-09-21", True),
    ("crint-zwe-aus-2026-09-20", "2026-09-23", False),
]


def main():
    failures = []

    for left, right, should_pair in NAME_CASES:
        score = pt.name_score(left, right)
        paired = score >= pt.MIN_NAME_SCORE
        if paired != should_pair:
            failures.append(
                f"name {left!r} vs {right!r}: scored {score:.2f}, "
                f"expected {'a pair' if should_pair else 'a reject'}")

    for slug, day, should_agree in DATE_CASES:
        agrees = pt.dates_agree(pt.slug_date(slug), datetime.date.fromisoformat(day))
        if agrees != should_agree:
            failures.append(
                f"date {slug} vs {day}: got {agrees}, expected {should_agree}")

    if pt.MAX_DATE_DRIFT_DAYS < 1:
        failures.append(
            "MAX_DATE_DRIFT_DAYS must stay at 1 or more: Polymarket dates slugs in US "
            "eastern time, so a fixture starting just after midnight UTC carries the "
            "previous day in its slug")

    if pt.slug_date("not-a-slug") is not None:
        failures.append("slug_date should return None when there is no date")

    for line in failures:
        print("FAIL " + line)
    print(f"{len(NAME_CASES) + len(DATE_CASES) + 1} checks, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
