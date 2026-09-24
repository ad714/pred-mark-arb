import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "live-edge"))
sys.path.insert(0, str(ROOT / "market-scanner"))

import requests
import dns_bypass
from src.fetch.clob_book import fetch_books

dns_bypass.install()

GAMMA = "https://gamma-api.polymarket.com/events"
FIXTURE = re.compile(r"^([a-z0-9]+)-[a-z0-9]+-[a-z0-9]+-(\d{4}-\d{2}-\d{2})$")
TAGS = ("soccer", "football")
EDGE_LOW, EDGE_HIGH = 0.65, 0.85
BREAKEVEN = 0.029
SNAPSHOT_GAP = 7200
BANDS = ((0.00, 0.20), (0.20, 0.35), (0.35, 0.50),
         (0.50, 0.65), (0.65, 0.85), (0.85, 1.01))


def quote_key(row):
    return (row.get("quoted"), row.get("bid"), row.get("ask"))


def band_of(price):
    for low, high in BANDS:
        if low <= price < high:
            return f"{low:.2f}-{high:.2f}"
    return "other"


def fetch_fixtures(session, now):
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now.strftime("%Y-%m-%d")
    events = {}
    for tag in TAGS:
        for offset in range(0, 2000, 100):
            try:
                response = session.get(GAMMA, params={
                    "limit": 100, "offset": offset, "closed": "false",
                    "active": "true", "tag_slug": tag, "end_date_min": stamp,
                }, timeout=30)
                page = response.json()
            except (requests.RequestException, ValueError):
                break
            if not isinstance(page, list) or not page:
                break
            for event in page:
                found = FIXTURE.match(event.get("slug") or "")
                if found and found.group(2) >= today:
                    events[event["slug"]] = (event, found.group(1), found.group(2))
            if len(page) < 100:
                break
    return events


def collect(session, now):
    fixtures = fetch_fixtures(session, now)
    legs, tokens = [], []
    for slug, (event, league, day) in fixtures.items():
        for market in event.get("markets") or []:
            if not market.get("acceptingOrders"):
                continue
            try:
                ids = json.loads(market.get("clobTokenIds") or "[]")
                prices = [float(p) for p in json.loads(market.get("outcomePrices") or "[]")]
            except (ValueError, TypeError):
                continue
            if not ids or not prices:
                continue
            legs.append({
                "fixture": slug, "league": league, "match_date": day,
                "market": market.get("slug"), "question": market.get("question"),
                "token": ids[0], "quoted": prices[0],
                "liquidity": event.get("liquidity"),
                "volume24hr": event.get("volume24hr"),
            })
            tokens.append(ids[0])

    books = {}
    if tokens:
        try:
            books = fetch_books(tokens)
        except Exception as exc:
            print(f"book fetch failed: {type(exc).__name__}: {exc}")

    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for leg in legs:
        book = books.get(leg["token"]) or {}
        bids, asks = book.get("bids") or [], book.get("asks") or []
        leg["bid"] = bids[0][0] if bids else None
        leg["ask"] = asks[0][0] if asks else None
        leg["bid_size"] = bids[0][1] if bids else None
        leg["ask_size"] = asks[0][1] if asks else None
        leg["spread"] = (round(leg["ask"] - leg["bid"], 4)
                         if leg["bid"] is not None and leg["ask"] is not None else None)
        leg["band"] = band_of(leg["quoted"])
        leg["in_edge_band"] = EDGE_LOW <= leg["quoted"] <= EDGE_HIGH
        leg["tradeable"] = bool(leg["in_edge_band"] and leg["spread"] is not None
                                and leg["spread"] < BREAKEVEN)
        leg["t"] = stamp
    return legs


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "data" / "football.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    legs = collect(requests.Session(), now)

    seen, last, newest_full = set(), {}, None
    if out.exists():
        with open(out, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                seen.add((row.get("t"), row.get("market")))
                last[row.get("market")] = quote_key(row)
                if row.get("snapshot"):
                    newest_full = row.get("t")

    full = True
    if newest_full:
        try:
            marked = datetime.strptime(newest_full, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            full = (now - marked).total_seconds() >= SNAPSHOT_GAP
        except ValueError:
            full = True

    added = 0
    with open(out, "a", encoding="utf-8") as handle:
        for leg in legs:
            if (leg["t"], leg["market"]) in seen:
                continue
            key = quote_key(leg)
            if not full and last.get(leg["market"]) == key:
                continue
            last[leg["market"]] = key
            if full:
                leg["snapshot"] = True
            handle.write(json.dumps(leg) + "\n")
            added += 1

    edge = [l for l in legs if l["in_edge_band"]]
    good = [l for l in edge if l["tradeable"]]
    print(f"sampled {len(legs)} markets across {len({l['fixture'] for l in legs})} fixtures")
    print(f"  in 0.65-0.85 edge band : {len(edge)} ({len(edge)/max(len(legs),1)*100:.1f}%)")
    print(f"  of those, spread < {BREAKEVEN}: {len(good)}")
    for leg in good:
        print(f"    {leg['market']:<38} {leg['quoted']:.3f}  spread {leg['spread']:.3f}")
    print(f"  appended {added} rows ({'snapshot' if full else 'changes'}) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
