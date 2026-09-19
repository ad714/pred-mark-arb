import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

import dns_bypass

GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
DATA_TRADES = "https://data-api.polymarket.com/trades"
CRICKET_TAG = 517
MAIN_MARKET_SLUG = re.compile(r"^cri[a-z0-9]*-[a-z0-9]+-[a-z0-9]+-\d{4}-\d{2}-\d{2}$")
PAGE_LIMIT = 100
ACTIVITY_WINDOW_S = 300
ACTIVITY_MIN_TRADES = 3


def recent_trade_count(session, condition_id):
    try:
        response = session.get(
            DATA_TRADES, params={"market": condition_id, "limit": 20}, timeout=15
        )
        response.raise_for_status()
        trades = response.json()
    except (requests.RequestException, ValueError):
        return 0
    now = int(time.time())
    return sum(1 for t in trades if now - t.get("timestamp", 0) <= ACTIVITY_WINDOW_S)


def discover(min_price, max_price, with_activity=True):
    session = requests.Session()
    events = []
    for offset in range(0, 1500, PAGE_LIMIT):
        response = session.get(
            GAMMA_EVENTS,
            params={
                "tag_id": CRICKET_TAG,
                "closed": "false",
                "limit": PAGE_LIMIT,
                "offset": offset,
                "order": "startDate",
                "ascending": "false",
            },
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        events.extend(page)

    candidates = {}
    for event in events:
        slug = event.get("slug") or ""
        if not MAIN_MARKET_SLUG.match(slug):
            continue

        markets = event.get("markets") or []
        if not markets:
            continue

        try:
            prices = [float(p) for p in json.loads(markets[0].get("outcomePrices") or "[]")]
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        if len(prices) != 2:
            continue

        favourite = max(prices)
        competitive = min_price <= favourite <= max_price
        closed = bool(event.get("closed"))

        active_trades = 0
        if with_activity and competitive and not closed:
            active_trades = recent_trade_count(session, markets[0].get("conditionId"))

        candidates[slug] = {
            "slug": slug,
            "title": (event.get("title") or "")[:60],
            "favourite": favourite,
            "recent_trades": active_trades,
            "competitive": competitive,
            "closed": closed,
            "in_play": active_trades >= ACTIVITY_MIN_TRADES,
        }
    return candidates


def spawn(slug, out_dir, interval):
    out_path = out_dir / f"poly_{slug}.jsonl"
    log_path = out_dir / f"poly_{slug}.log"
    handle = open(log_path, "a", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "record_polymarket.py",
            slug,
            "--interval",
            str(interval),
            "--out",
            str(out_path),
            "--verbose",
        ],
        stdout=handle,
        stderr=subprocess.STDOUT,
        cwd=Path(__file__).parent,
    )
    return {"process": process, "log": handle, "out": out_path}


def spawn_cricket(out_dir, interval):
    log_path = out_dir / "cricket.log"
    handle = open(log_path, "a", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "record_cricket.py",
            "--interval",
            str(interval),
            "--out",
            str(out_dir / "cricket_events.jsonl"),
            "--verbose",
        ],
        stdout=handle,
        stderr=subprocess.STDOUT,
        cwd=Path(__file__).parent,
    )
    return {"process": process, "log": handle}


def stamp():
    return time.strftime("%H:%M:%S")


def run(out_dir, poll_seconds, min_price, max_price, poly_interval, cricket_interval):
    dns_bypass.install()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"watching cricket markets -> {out_dir}")
    print(f"attach window: favourite price between {min_price} and {max_price}")
    print("one cricket recorder covers all matches; one poly recorder per market\n")

    cricket = spawn_cricket(out_dir, cricket_interval)
    print(f"[{stamp()}] cricket recorder up (pid {cricket['process'].pid})")

    attached = {}
    manifest_path = out_dir / "manifest.jsonl"

    try:
        while True:
            try:
                candidates = discover(min_price, max_price)
            except requests.RequestException as exc:
                print(f"[{stamp()}] discovery failed: {type(exc).__name__}")
                time.sleep(poll_seconds)
                continue

            if cricket["process"].poll() is not None:
                cricket["log"].close()
                cricket = spawn_cricket(out_dir, cricket_interval)
                print(f"[{stamp()}] cricket recorder died; respawned (pid {cricket['process'].pid})")

            for slug, record in list(attached.items()):
                if record is None or record["process"].poll() is None:
                    continue
                record["log"].close()
                attached[slug] = spawn(slug, out_dir, poly_interval)
                print(f"[{stamp()}] poly recorder for {slug} died; respawned")

            for slug, candidate in candidates.items():
                if slug in attached:
                    continue
                if not candidate["competitive"] or not candidate["in_play"]:
                    continue

                attached[slug] = spawn(slug, out_dir, poly_interval)
                print(
                    f"[{stamp()}] ATTACH {slug} "
                    f"(favourite {candidate['favourite']:.3f}, "
                    f"{candidate['recent_trades']} trades/5min) {candidate['title']}"
                )
                with open(manifest_path, "a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            {
                                "slug": slug,
                                "title": candidate["title"],
                                "attached_ms": int(time.time() * 1000),
                                "favourite_at_attach": candidate["favourite"],
                            }
                        )
                        + "\n"
                    )

            for slug, record in list(attached.items()):
                candidate = candidates.get(slug)
                resolved = candidate is None or candidate["closed"]
                if not resolved:
                    continue
                if record is not None:
                    record["process"].terminate()
                    record["log"].close()
                    reason = "market closed" if candidate else "market gone"
                    print(f"[{stamp()}] DETACH {slug} ({reason})")
                del attached[slug]

            in_play = [s for s, c in candidates.items() if c["in_play"]]
            print(
                f"[{stamp()}] {len(in_play)} in-play cricket markets, "
                f"{len(attached)} recording"
            )
            time.sleep(poll_seconds)

    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        for record in attached.values():
            if record is not None:
                record["process"].terminate()
                record["log"].close()
        cricket["process"].terminate()
        cricket["log"].close()


def main():
    parser = argparse.ArgumentParser(
        description="Auto-attach recorders to live, competitive cricket markets."
    )
    parser.add_argument("--out", type=Path, default=Path("data/sessions"))
    parser.add_argument("--poll", type=float, default=60.0)
    parser.add_argument("--min-price", type=float, default=0.15)
    parser.add_argument("--max-price", type=float, default=0.85)
    parser.add_argument("--poly-interval", type=float, default=1.0)
    parser.add_argument("--cricket-interval", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        dns_bypass.install()
        candidates = discover(args.min_price, args.max_price)
        in_play = {s: c for s, c in candidates.items() if c["in_play"]}
        print(f"{len(candidates)} cricket main-markets, {len(in_play)} in-play\n")
        for candidate in sorted(
            candidates.values(), key=lambda c: (not c["in_play"], not c["competitive"])
        ):
            if candidate["in_play"] and candidate["competitive"]:
                flag = "WOULD ATTACH"
            elif candidate["in_play"]:
                flag = "in-play/1sided"
            else:
                flag = "dormant     "
            print(
                f"  {flag:<14}  fav {candidate['favourite']:.3f}  "
                f"{candidate['recent_trades']:>2}tr/5m  "
                f"{candidate['slug']:<44} {candidate['title']}"
            )
        return

    run(
        args.out,
        args.poll,
        args.min_price,
        args.max_price,
        args.poly_interval,
        args.cricket_interval,
    )


if __name__ == "__main__":
    sys.exit(main())
