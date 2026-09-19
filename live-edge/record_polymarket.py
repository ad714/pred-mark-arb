import argparse
import json
import sys
import time
from pathlib import Path

import requests

import dns_bypass

GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
DATA_TRADES = "https://data-api.polymarket.com/trades"
CLOB_BOOK = "https://clob.polymarket.com/book"


def resolve_market(slug):
    response = requests.get(GAMMA_EVENTS, params={"slug": slug}, timeout=20)
    response.raise_for_status()
    events = response.json()
    if not events:
        raise SystemExit(f"no event for slug '{slug}'")

    for market in events[0].get("markets", []):
        if market.get("slug") == slug:
            token_ids = json.loads(market["clobTokenIds"])
            outcomes = json.loads(market["outcomes"])
            return {
                "condition_id": market["conditionId"],
                "question": market.get("question"),
                "tokens": dict(zip(outcomes, token_ids)),
            }
    raise SystemExit(f"event found but no market matching slug '{slug}'")


def fetch_trades(session, condition_id, limit):
    response = session.get(
        DATA_TRADES, params={"market": condition_id, "limit": limit}, timeout=10
    )
    response.raise_for_status()
    return response.json()


def fetch_midpoint(session, token_id):
    response = session.get(CLOB_BOOK, params={"token_id": token_id}, timeout=10)
    response.raise_for_status()
    book = response.json()
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    best_bid = max((float(b["price"]) for b in bids), default=None)
    best_ask = min((float(a["price"]) for a in asks), default=None)
    mid = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": round(mid, 4) if mid is not None else None,
        "bid_depth": round(sum(float(b["size"]) for b in bids), 2),
        "ask_depth": round(sum(float(a["size"]) for a in asks), 2),
    }


def trade_key(trade):
    return (
        trade.get("transactionHash"),
        trade.get("proxyWallet"),
        trade.get("asset"),
        trade.get("size"),
        trade.get("price"),
    )


def run(slug, interval, out_path, quote_outcome, verbose):
    dns_bypass.install()
    market = resolve_market(slug)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"market   : {market['question']}")
    print(f"condition: {market['condition_id']}")
    for outcome, token in market["tokens"].items():
        print(f"  {outcome:<14} {token}")

    quote_name = quote_outcome or list(market["tokens"])[-1]
    quote_token = market["tokens"][quote_name]
    print(f"quoting  : {quote_name}")
    print(f"recording -> {out_path}  (interval {interval}s, Ctrl+C to stop)\n")

    session = requests.Session()
    seen = set()
    poll_count = 0
    fail_count = 0
    last_mid = None
    primed = False

    with open(out_path, "a", encoding="utf-8") as handle:
        while True:
            cycle_start = time.perf_counter()
            poll_count += 1

            try:
                trades = fetch_trades(session, market["condition_id"], 100)
                quote = fetch_midpoint(session, quote_token)
                recv_ms = int(time.time() * 1000)
            except (requests.RequestException, ValueError, KeyError) as exc:
                fail_count += 1
                print(f"[poll {poll_count}] FAILED {type(exc).__name__}: {exc}")
                time.sleep(interval)
                continue

            fresh = []
            for trade in trades:
                key = trade_key(trade)
                if key in seen:
                    continue
                seen.add(key)
                fresh.append(trade)

            if not primed:
                primed = True
                print(f"primed with {len(fresh)} existing trades\n")
                fresh = []

            for trade in sorted(fresh, key=lambda t: t.get("timestamp", 0)):
                record = {
                    "event": "trade",
                    "recv_ms": recv_ms,
                    "iso": time.strftime("%H:%M:%S", time.gmtime(recv_ms / 1000)),
                    "api_ts": trade.get("timestamp"),
                    "lag_s": recv_ms // 1000 - trade.get("timestamp", 0),
                    "wallet": trade.get("proxyWallet"),
                    "name": trade.get("name") or trade.get("pseudonym"),
                    "side": trade.get("side"),
                    "outcome": trade.get("outcome"),
                    "price": trade.get("price"),
                    "size": trade.get("size"),
                    "notional": round(
                        (trade.get("size") or 0) * (trade.get("price") or 0), 2
                    ),
                    "tx": trade.get("transactionHash"),
                }
                handle.write(json.dumps(record) + "\n")
                if record["notional"] >= 20:
                    print(
                        f"  [{record['iso']}] {record['side']:<4} "
                        f"{record['size']:>8.1f} {record['outcome']:<10} "
                        f"@ {record['price']:.3f}  ${record['notional']:>8.2f}  "
                        f"lag {record['lag_s']}s  {record['name']}"
                    )

            if quote["mid"] is not None and quote["mid"] != last_mid:
                record = {
                    "event": "quote",
                    "recv_ms": recv_ms,
                    "iso": time.strftime("%H:%M:%S", time.gmtime(recv_ms / 1000)),
                    "outcome": quote_name,
                    **quote,
                }
                handle.write(json.dumps(record) + "\n")
                if verbose:
                    print(
                        f"  [{record['iso']}] QUOTE {quote_name} "
                        f"mid {quote['mid']:.3f} "
                        f"({quote['best_bid']:.3f}/{quote['best_ask']:.3f}) "
                        f"depth {quote['bid_depth']:.0f}/{quote['ask_depth']:.0f}"
                    )
                last_mid = quote["mid"]

            handle.flush()

            if verbose and poll_count % 20 == 0:
                print(
                    f"[poll {poll_count}] {len(seen)} trades seen, {fail_count} failures"
                )

            time.sleep(max(0.0, interval - (time.perf_counter() - cycle_start)))


def main():
    parser = argparse.ArgumentParser(
        description="Record Polymarket trade tape and top-of-book for one market."
    )
    parser.add_argument("slug")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=Path("data/poly_events.jsonl"))
    parser.add_argument("--quote", default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    try:
        run(args.slug, args.interval, args.out, args.quote, args.verbose)
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    sys.exit(main())
