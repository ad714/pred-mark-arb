import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

LIVE_SCORES_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cache-Control": "no-cache",
}
CHUNK = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)')
BENIGN_EVENTS = {"none", "all", "over-break", "udrs", "team_fifty", "team_hundred"}
RUN_WORDS = {"none", "one", "two", "three", "four", "five", "six", "byes", "leg-byes"}


class ParseFailed(RuntimeError):
    pass


def decode_blob(html):
    chunks = CHUNK.findall(html)
    if not chunks:
        raise ParseFailed("no flight chunks")
    return "".join(json.loads('"' + c + '"') for c in chunks)


def object_bounds(blob, key_index):
    start = blob.rfind("{", 0, key_index)
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(blob)):
        c = blob[i]
        if escaped:
            escaped = False
            continue
        if c == "\\":
            escaped = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise ParseFailed("unbalanced braces")


def extract_balls(blob):
    balls = []
    for hit in re.finditer(r'"commText"\s*:', blob):
        try:
            start, end = object_bounds(blob, hit.start())
            obj = json.loads(blob[start:end])
        except (ParseFailed, json.JSONDecodeError):
            continue
        if obj.get("commType") != "commentary":
            continue
        if "timestamp" not in obj:
            continue
        balls.append(obj)
    return balls


def resolve_match(match_substring):
    from record_cricket import extract_matches

    html = requests.get(LIVE_SCORES_URL, headers=HEADERS, timeout=20).text
    matches = extract_matches(html)
    for match_id, match in matches.items():
        info = match["matchInfo"]
        t1 = (info.get("team1") or {}).get("teamSName", "")
        t2 = (info.get("team2") or {}).get("teamSName", "")
        label = f"{t1} v {t2}"
        if match_substring.lower() in label.lower():
            return match_id, label
    raise SystemExit(f"no live match matching '{match_substring}'")


def commentary_url(match_id):
    return f"https://www.cricbuzz.com/live-cricket-scores/{match_id}/x"


def classify(event):
    flags = [str(e).lower() for e in (event or [])]
    unknown = [f for f in flags if f not in BENIGN_EVENTS and f not in RUN_WORDS]
    return unknown


def run(match_id, label, interval, out_path, verbose):
    session = requests.Session()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    url = commentary_url(match_id)

    print(f"commentary recorder: {label} (match {match_id})")
    print(f"recording -> {out_path}  (interval {interval}s, Ctrl+C to stop)\n")

    seen = set()
    poll_count = 0
    fail_count = 0
    primed = False

    with open(out_path, "a", encoding="utf-8") as handle:
        while True:
            cycle_start = time.perf_counter()
            poll_count += 1
            try:
                html = session.get(url, headers=HEADERS, timeout=15).text
                balls = extract_balls(decode_blob(html))
                recv_ms = int(time.time() * 1000)
            except (requests.RequestException, ParseFailed) as exc:
                fail_count += 1
                print(f"[poll {poll_count}] FAILED {type(exc).__name__}: {exc}")
                time.sleep(interval)
                continue

            fresh = []
            for ball in balls:
                key = (ball.get("inningsId"), ball.get("ballMetric"), ball.get("timestamp"))
                if key in seen:
                    continue
                seen.add(key)
                fresh.append(ball)

            if not primed:
                primed = True
                print(f"primed with {len(fresh)} existing balls\n")
                fresh = []

            for ball in sorted(fresh, key=lambda b: b.get("timestamp", 0)):
                event = ball.get("event")
                comm = ball.get("commText")
                unknown = classify(event)
                record = {
                    "cb_ms": ball.get("timestamp"),
                    "recv_ms": recv_ms,
                    "iso": time.strftime("%H:%M:%S", time.gmtime(ball.get("timestamp", 0) / 1000)),
                    "innings": ball.get("inningsId"),
                    "over_ball": ball.get("ballMetric"),
                    "team": ball.get("teamName"),
                    "event": event,
                    "event_unknown": unknown,
                    "batsman": (ball.get("batsmanDetails") or {}).get("playerName"),
                    "bowler": (ball.get("bowlerDetails") or {}).get("playerName"),
                    "text": comm,
                }
                handle.write(json.dumps(record) + "\n")
                if verbose or unknown:
                    tag = f"EVENT[{','.join(unknown)}]" if unknown else "ball"
                    print(f"  [{record['iso']}] {tag} {record['over_ball']}: {comm}")
            handle.flush()

            if poll_count % 20 == 0:
                print(f"[poll {poll_count}] {len(seen)} balls seen, {fail_count} failures")

            time.sleep(max(0.0, interval - (time.perf_counter() - cycle_start)))


def main():
    parser = argparse.ArgumentParser(
        description="Record ball-by-ball Cricbuzz commentary with per-ball timestamps."
    )
    parser.add_argument("match", help="substring of team short names, e.g. 'SUL v LDN'")
    parser.add_argument("--interval", type=float, default=4.0)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--match-id", type=int, default=None)
    args = parser.parse_args()

    if args.match_id:
        match_id, label = args.match_id, args.match
    else:
        match_id, label = resolve_match(args.match)

    out_path = args.out or Path(f"data/commentary_{match_id}.jsonl")

    try:
        run(match_id, label, args.interval, out_path, args.verbose)
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    sys.exit(main())
