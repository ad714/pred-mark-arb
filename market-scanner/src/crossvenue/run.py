"""Hourly cross-venue watch: Pascal against Polymarket, soonest resolution first.

Every pair here is an exact join on Polymarket's own outcome token id, so a crossed
book is a genuine lock rather than two similar-sounding questions. Both legs are
buys and the pair pays $1 whichever way it lands, so the only judgement left is
whether the fill is worth the effort.

Ranked by time to resolution, not by profit: capital that comes back tonight can be
used again tomorrow, and a lock held for two years is not a lock worth having.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
LIVE_EDGE = ROOT / "live-edge"
if LIVE_EDGE.is_dir():
    sys.path.insert(0, str(LIVE_EDGE))
    import dns_bypass

    dns_bypass.install()

from src.crossvenue.book import ladder, walk
from src.crossvenue import pascal

DATA = ROOT / "docs" / "data"
LATEST = DATA / "crossvenue.json"
HISTORY = DATA / "crossvenue.jsonl"
ALERT = ROOT / "alert.json"


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital", type=float, default=25.0,
                        help="most to tie up across both legs of one pair")
    parser.add_argument("--horizon-days", type=float, default=7.0,
                        help="ignore anything resolving later than this")
    parser.add_argument("--min-profit", type=float, default=0.10,
                        help="alert bar, in dollars of locked profit")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def in_horizon(market, horizon_days, now_ms):
    resolves = market.get("resolves_ms")
    if not resolves:
        return None
    days = (int(resolves) - now_ms) / 86_400_000
    return days if 0 < days <= horizon_days else None


def price(market, pascal_book, poly_book, capital, poly_fee):
    """Best locked fill for one pair, or None if neither direction crosses.

    Both venues take a fee, so each leg is charged at its own venue's rate.
    """
    pascal_asks = ladder(pascal_book.get("asks"), ascending=True)
    pascal_bids = ladder(pascal_book.get("bids"), ascending=False)
    poly_asks = ladder(poly_book.get("asks"), ascending=True)
    poly_bids = ladder(poly_book.get("bids"), ascending=False)
    rate, exponent = poly_fee
    pascal_rate = market["taker_fee"]

    candidates = [
        ("buy Pascal, buy NO on Polymarket",
         walk(pascal_asks, poly_bids, pascal_rate, rate, capital, exponent)),
        ("buy Polymarket, buy NO on Pascal",
         walk(poly_asks, pascal_bids, rate, pascal_rate, capital, exponent)),
    ]
    best_side, best = None, None
    for side, result in candidates:
        if result and (best is None or result["profit"] > best["profit"]):
            best_side, best = side, result
    if best is None:
        return None
    return {**best, "side": best_side}


def scan(args):
    now_ms = int(time.time() * 1000)
    markets = pascal.fetch_markets()
    watched = []
    for market in markets:
        days = in_horizon(market, args.horizon_days, now_ms)
        if days is not None:
            watched.append({**market, "days": days})
    watched.sort(key=lambda m: m["days"])

    session = requests.Session()
    pascal_books, pascal_missing = pascal.fetch_books(
        [m["symbol"] for m in watched], session)
    poly_books, poly_missing = pascal.fetch_poly_books(
        [m["token"] for m in watched], session)
    poly_fees = pascal.fetch_poly_fees([m["slug"] for m in watched], session)
    fallback = (pascal.DEFAULT_POLY_FEE, 1)

    hits = []
    for market in watched:
        result = price(market, pascal_books.get(market["symbol"]) or {},
                       poly_books.get(market["token"]) or {}, args.capital,
                       poly_fees.get(market["slug"], fallback))
        if result and result["profit"] > 0:
            hits.append({
                "symbol": market["symbol"], "slug": market["slug"],
                "event": market["event"], "outcome": market["outcome"],
                "days": round(market["days"], 3),
                "resolves": datetime.fromtimestamp(int(market["resolves_ms"]) / 1000,
                                                   timezone.utc).isoformat(),
                "side": result["side"],
                "profit": round(result["profit"], 4),
                "capital": round(result["capital"], 2),
                "shares": round(result["shares"], 1),
                "edge": round(result["edge"], 4),
                "fees": round(result["fees"], 4),
                "buy": result["buy"], "sell": result["sell"],
            })

    hits.sort(key=lambda hit: hit["days"])
    return {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pairs_joined": len(markets),
        "pairs_watched": len(watched),
        "capital_cap": args.capital,
        "horizon_days": args.horizon_days,
        "unread_pascal": pascal_missing,
        "unread_poly": poly_missing,
        "hits": hits,
    }


def report(snapshot, args):
    print(f"{snapshot['pairs_watched']} exactly-joined pairs resolve within "
          f"{args.horizon_days:g} days (of {snapshot['pairs_joined']} joined)")
    print(f"capital capped at ${args.capital:g} across both legs")
    unread = snapshot.get("unread_pascal", 0) + snapshot.get("unread_poly", 0)
    if unread:
        print(f"WARNING: {unread} book(s) unread "
              f"({snapshot['unread_pascal']} Pascal, {snapshot['unread_poly']} "
              "Polymarket). This run is incomplete, not a clean negative.")
    print()
    if not snapshot["hits"]:
        print("no crossed books")
        return
    print(f"{'resolves':>9}  {'profit':>8}  {'capital':>8}  {'edge':>7}  pair")
    for hit in snapshot["hits"][:args.top]:
        when = (f"{hit['days'] * 24:.1f}h" if hit["days"] < 1
                else f"{hit['days']:.1f}d")
        print(f"{when:>9}  ${hit['profit']:>7.2f}  ${hit['capital']:>7.2f}  "
              f"{hit['edge']:>7.4f}  {hit['event']} | {hit['outcome']}")
        print(f"{'':>9}  {hit['side']} at {hit['buy']:.3f} against {hit['sell']:.3f}"
              f"  [{hit['symbol']}]")


def write(snapshot, args):
    DATA.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"checked_at": snapshot["checked_at"],
                                 "watched": snapshot["pairs_watched"],
                                 "hits": snapshot["hits"]}) + "\n")

    alertable = [h for h in snapshot["hits"] if h["profit"] >= args.min_profit]
    ALERT.write_text(json.dumps({"checked_at": snapshot["checked_at"],
                                 "hits": alertable}, indent=1), encoding="utf-8")
    return alertable


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    snapshot = scan(args)
    report(snapshot, args)
    if args.no_write:
        return 0
    alertable = write(snapshot, args)
    if alertable:
        print(f"\n{len(alertable)} pair(s) over the ${args.min_profit:g} alert bar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
