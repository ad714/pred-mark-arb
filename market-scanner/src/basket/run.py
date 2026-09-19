import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LIVE_EDGE = Path(__file__).resolve().parents[3] / "live-edge"
if LIVE_EDGE.is_dir():
    sys.path.insert(0, str(LIVE_EDGE))
    import dns_bypass

    dns_bypass.install()

from src.basket.basket import assess_event, event_legs, quoted_sum
from src.fetch.clob_book import fetch_books
from src.fetch.poly import PolymarketUnreachable
from src.fetch.poly_events import fetch_active_events, load_raw, save_raw

OUT_FILE = Path("data/derived/basket.json")
RULE = "=" * 78
FEE_MODEL = "taker fee = shares * rate * p * (1 - p), charged on every leg as it fills"


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="basket",
        description="Find negRisk events whose full ask basket costs less than $1.00 a share.",
    )
    parser.add_argument("--offline", action="store_true", help="score the saved snapshot")
    parser.add_argument("--max-events", type=int, default=2100)
    parser.add_argument("--gate", type=float, default=1.0,
                        help="pull books only where the quoted ask sum is below this")
    parser.add_argument("--min-net", type=float, default=1.0,
                        help="hide events whose best net profit is under this")
    parser.add_argument("--min-days", type=float, default=0.0,
                        help="hide events resolving sooner than this many days")
    parser.add_argument("--include-expired", action="store_true",
                        help="keep events already past their end date")
    parser.add_argument("--complete-only", action="store_true",
                        help="keep only events where every outcome is buyable")
    parser.add_argument("--show-traps", action="store_true",
                        help="also show baskets that cost over $1.00 once the unbuyable legs "
                             "are charged at their own market price")
    parser.add_argument("--top", type=int, default=25)
    return parser.parse_args(argv)


def gather(events, gate):
    candidates = []
    tokens = []
    skipped = {"not_negrisk": 0, "too_few_legs": 0, "quoted_over_gate": 0}

    for event in events:
        if not event.get("negRisk"):
            skipped["not_negrisk"] += 1
            continue
        legs = event_legs(event)
        total, quoted, _ = quoted_sum(legs)
        if quoted < 2:
            skipped["too_few_legs"] += 1
            continue
        if total >= gate:
            skipped["quoted_over_gate"] += 1
            continue
        candidates.append(event)
        tokens.extend(leg["token"] for leg in legs)

    return candidates, tokens, skipped


def keep(row, args):
    if row["peak_net"] < args.min_net:
        return False
    if args.complete_only and not row["complete_basket"]:
        return False
    if not args.show_traps and row["full_cost_per_share"] >= 1.0:
        return False
    if row["days_left"] is not None:
        if not args.include_expired and row["days_left"] < 0:
            return False
        if row["days_left"] < args.min_days:
            return False
    return True


def table(rows, top):
    print(f"{'net$':>8}{'size':>7}{'cap$':>9}{'ret%':>7}{'/share':>8}{'+dark':>8}"
          f"{'legs':>6}{'prcd':>6}{'unk':>5}{'real':>6}{'days':>7}{'vol24h':>10}  event")
    for row in rows[:top]:
        days = f"{row['days_left']:.0f}" if row["days_left"] is not None else "-"
        full = "-" if row["complete_basket"] else f"{row['full_cost_per_share']:.3f}"
        print(f"{row['peak_net']:>8.2f}{row['peak_size']:>7.0f}{row['peak_capital']:>9.2f}"
              f"{row['peak_return_pct']:>7.1f}{row['cost_per_share_peak']:>8.3f}{full:>8}"
              f"{row['legs_buyable']:>6}"
              f"{row['legs_dark'] - row['legs_unknown']:>6}{row['legs_unknown']:>5}"
              f"{row['legs_unknown_named']:>6}{days:>7}"
              f"{row['volume_24h']:>10,}  {row['title'][:42]}")


def report(rows, args, scanned, candidates, skipped, traps):
    print()
    print(f"Scanned {scanned} active events "
          f"({skipped['not_negrisk']} not negRisk, "
          f"{skipped['too_few_legs']} under two quoted legs, "
          f"{skipped['quoted_over_gate']} quoted at or over ${args.gate:.2f}).")
    print(f"Walked the full ask ladder on {candidates} candidates.")
    print(f"Fees: {FEE_MODEL}")
    if traps and not args.show_traps:
        print(f"Hid {traps} baskets that cost over $1.00 once the unbuyable legs are charged "
              f"at their own market price. Use --show-traps to see them.")

    complete = [row for row in rows if row["complete_basket"]]
    partial = [row for row in rows if not row["complete_basket"]]

    print()
    print(RULE)
    print(f"COMPLETE BASKETS ({len(complete)}) - every outcome is buyable, no judgement needed")
    print(RULE)
    if complete:
        table(complete, args.top)
    else:
        print("None right now. This is the rare case; most negRisk events have dark legs.")

    print()
    print(RULE)
    print(f"NEEDS A CALL ({len(partial)}) - some outcomes cannot be bought at any price")
    print(RULE)
    print("prcd = unbuyable outcomes that have traded, so they carry a real market price.")
    print("unk  = unbuyable outcomes that have never traded and nobody bids on. No price exists.")
    print("real = unk legs whose name is a real contender, not an auto-generated placeholder.")
    print()
    print("+dark charges every priced unbuyable leg at its own market price on top of the")
    print("basket, so under $1.00 means the mispricing survives that charge. Then read the")
    print("real column: 0 is the Morocco shape and the one worth looking at, because every")
    print("real leg is an outcome that can win and that you cannot hedge.")
    print()
    if partial:
        table(partial, args.top)
        print()
        for row in partial[:min(args.top, 6)]:
            print(f"  {row['title'][:60]}")
            priced = row["legs_dark"] - row["legs_unknown"]
            print(f"    {priced} priced unbuyable (dearest {row['dark_mark_max']:.3f}), "
                  f"{row['legs_unknown']} with no price at all")
            if row["unknown_named"]:
                print(f"    REAL CONTENDERS you cannot buy: "
                      f"{', '.join(row['unknown_named'][:6])}")
            elif row["unknown_names"]:
                print(f"    all placeholders: {', '.join(row['unknown_names'][:6])}")
    else:
        print("None.")

    best = next(iter(complete or partial), None)
    if not best:
        return
    print()
    print("-" * 78)
    print(f"Best by profit at peak size: {best['title']}")
    print(f"  {best['url']}")
    print(f"  buy {best['peak_size']:.0f} of each of {best['legs_buyable']} legs for "
          f"${best['peak_capital']:.2f}, collect ${best['peak_size']:.0f}, "
          f"fees ${best['peak_fee']:.2f}, net ${best['peak_net']:.2f}")
    print(f"  linchpin is {best['linchpin']} at ${best['linchpin_cost']:.2f} of the basket. "
          f"Fill that one first, alone.")
    if not best["complete_basket"]:
        print(f"  WARNING: {best['legs_dark']} outcomes are unbuyable "
              f"({best['legs_unknown']} of them with no market price at all). "
              f"If one of them wins, the whole ${best['peak_capital']:.2f} is lost.")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv if argv is not None else sys.argv[1:])
    now = datetime.now(timezone.utc)

    try:
        events = load_raw() if args.offline else fetch_active_events(args.max_events)
    except PolymarketUnreachable as exc:
        print(f"\n{exc}\n")
        return 1

    if not args.offline:
        save_raw(events)

    candidates, tokens, skipped = gather(events, args.gate)
    print(f"\nReading {len(tokens)} order books across {len(candidates)} candidate events...")

    try:
        books = fetch_books(tokens)
    except PolymarketUnreachable as exc:
        print(f"\n{exc}\n")
        return 1

    rows = []
    traps = 0
    for event in candidates:
        row = assess_event(event, books, now=now)
        if not row:
            continue
        if row["full_cost_per_share"] >= 1.0:
            traps += 1
        if keep(row, args):
            rows.append(row)

    rows.sort(key=lambda row: row["peak_net"], reverse=True)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at": now.isoformat(),
                "events_scanned": len(events),
                "candidates_walked": len(candidates),
                "fee_model": FEE_MODEL,
                "universe": f"top {len(events)} active events by 24h volume "
                            f"(gamma caps offset paging at 2000)",
                "filters": vars(args),
                "events": rows,
            },
            handle,
            indent=2,
        )

    report(rows, args, len(events), len(candidates), skipped, traps)
    print(f"\nFull detail -> {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
