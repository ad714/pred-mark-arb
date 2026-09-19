import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.fetch.poly import (
    PolymarketUnreachable,
    fetch_active_markets,
    load_raw,
    save_raw,
)
from src.normalize.poly_screen import normalize_screen_market
from src.screen.scores import is_screenable, screen_market

OUT_FILE = Path("data/derived/screener.json")


def build(raw_markets):
    now = datetime.now(timezone.utc)

    screened = []
    rejected = {}

    for raw in raw_markets:
        market = normalize_screen_market(raw, now=now)
        ok, reason = is_screenable(market)
        if not ok:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        screened.append(screen_market(market))

    screened.sort(key=lambda m: m["safety_score"], reverse=True)
    return screened, rejected


def main():
    offline = "--offline" in sys.argv

    try:
        raw_markets = load_raw() if offline else fetch_active_markets()
    except PolymarketUnreachable as exc:
        print(f"\n{exc}\n")
        return 1

    if not offline:
        save_raw(raw_markets)

    screened, rejected = build(raw_markets)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_fetched": len(raw_markets),
                "total_screened": len(screened),
                "rejected": rejected,
                "markets": screened,
            },
            handle,
            indent=2,
        )

    print(f"\nFetched {len(raw_markets)} markets, {len(screened)} passed the hard filters.")
    for reason, count in sorted(rejected.items(), key=lambda kv: -kv[1]):
        print(f"  excluded {count:>5}  {reason}")

    print(f"\nTop 15 by safety score -> {OUT_FILE}\n")
    print(f"{'safety':>6} {'exec':>5} {'res':>5} {'time':>5} {'days':>6}  question")
    for market in screened[:15]:
        print(
            f"{market['safety_score']:>6.1f} "
            f"{market['execution_score']:>5.1f} "
            f"{market['resolution_score']:>5.1f} "
            f"{market['time_score']:>5.1f} "
            f"{market['days_left']:>6.1f}  "
            f"{market['question'][:70]}"
        )

    print("\nOpen the dashboard with:")
    print("  python -m http.server 8000")
    print("  http://localhost:8000/web/screener.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
