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
FLIGHT_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)')


class ParseFailed(RuntimeError):
    pass


def decode_flight_payload(html):
    chunks = FLIGHT_CHUNK.findall(html)
    if not chunks:
        raise ParseFailed("no __next_f flight chunks found; page structure changed")
    return "".join(json.loads('"' + chunk + '"') for chunk in chunks)


def find_object_bounds(blob, key_index):
    start = blob.rfind("{", 0, key_index)
    if start == -1:
        raise ParseFailed("no opening brace before key")

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(blob)):
        char = blob[i]

        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1

    raise ParseFailed("unbalanced braces while scanning match object")


def extract_matches(html):
    blob = decode_flight_payload(html)
    matches = {}

    for hit in re.finditer(r'"matchInfo"\s*:', blob):
        try:
            start, end = find_object_bounds(blob, hit.start())
            obj = json.loads(blob[start:end])
        except (ParseFailed, json.JSONDecodeError):
            continue

        info = obj.get("matchInfo")
        if not isinstance(info, dict) or "matchId" not in info:
            continue
        matches[info["matchId"]] = obj

    if not matches:
        raise ParseFailed("flight payload decoded but contained no matches")
    return matches


def innings_snapshots(match):
    score = match.get("matchScore") or {}
    out = {}
    for team_key in ("team1Score", "team2Score"):
        for innings_key, innings in (score.get(team_key) or {}).items():
            if not isinstance(innings, dict):
                continue
            runs = innings.get("runs")
            wickets = innings.get("wickets")
            if runs is not None and wickets is None:
                wickets = 0
            out[f"{team_key}.{innings_key}"] = {
                "runs": runs,
                "wickets": wickets,
                "overs": innings.get("overs"),
            }
    return out


def describe(match):
    info = match["matchInfo"]
    team1 = (info.get("team1") or {}).get("teamSName", "?")
    team2 = (info.get("team2") or {}).get("teamSName", "?")
    return f"{team1} v {team2} ({info.get('matchDesc', '')})".strip()


def ratchet(previous, current):
    merged = dict(previous)
    for innings_key, now in current.items():
        before = merged.get(innings_key)
        if before is None:
            merged[innings_key] = dict(now)
            continue
        merged[innings_key] = {
            field: max(
                [v for v in (before.get(field), now.get(field)) if v is not None],
                default=None,
            )
            for field in ("runs", "wickets", "overs")
        }
    return merged


def diff_events(match_id, label, previous, current):
    events = []

    for innings_key, now in current.items():
        before = previous.get(innings_key)
        if before is None:
            continue

        if now["wickets"] is not None and before["wickets"] is not None:
            delta = now["wickets"] - before["wickets"]
            if delta > 0:
                events.append(
                    {
                        "event": "wicket",
                        "match_id": match_id,
                        "match": label,
                        "innings": innings_key,
                        "wickets_delta": delta,
                        "wickets": now["wickets"],
                        "runs": now["runs"],
                        "overs": now["overs"],
                    }
                )

        if now["runs"] is not None and before["runs"] is not None:
            run_delta = now["runs"] - before["runs"]
            if run_delta >= 4:
                events.append(
                    {
                        "event": "boundary",
                        "match_id": match_id,
                        "match": label,
                        "innings": innings_key,
                        "runs_delta": run_delta,
                        "runs": now["runs"],
                        "wickets": now["wickets"],
                        "overs": now["overs"],
                    }
                )

    return events


def write_event(handle, payload, wall_ms, monotonic_s):
    record = dict(payload)
    record["wall_ms"] = wall_ms
    record["monotonic_s"] = round(monotonic_s, 4)
    record["iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(wall_ms / 1000))
    handle.write(json.dumps(record) + "\n")
    handle.flush()
    return record


def run(interval, out_path, match_filter, verbose):
    session = requests.Session()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tracked = {}
    labels = {}
    poll_count = 0
    fail_count = 0

    print(f"recording -> {out_path}  (interval {interval}s, Ctrl+C to stop)")
    if match_filter:
        print(f"filter: substring '{match_filter}'")

    with open(out_path, "a", encoding="utf-8") as handle:
        while True:
            cycle_start = time.perf_counter()
            wall_ms = int(time.time() * 1000)
            poll_count += 1

            try:
                response = session.get(LIVE_SCORES_URL, headers=HEADERS, timeout=10)
                response.raise_for_status()
                matches = extract_matches(response.text)
                fetch_ms = (time.perf_counter() - cycle_start) * 1000
            except (requests.RequestException, ParseFailed) as exc:
                fail_count += 1
                print(f"[poll {poll_count}] FAILED: {type(exc).__name__}: {exc}")
                time.sleep(interval)
                continue

            for match_id, match in matches.items():
                label = describe(match)
                if match_filter and match_filter.lower() not in label.lower():
                    continue

                current = innings_snapshots(match)
                if not current:
                    continue

                labels[match_id] = label
                previous = tracked.get(match_id)

                if previous is None:
                    tracked[match_id] = current
                    if verbose:
                        print(f"  tracking: {label}")
                    continue

                for event in diff_events(match_id, label, previous, current):
                    event["fetch_ms"] = round(fetch_ms, 1)
                    record = write_event(handle, event, wall_ms, time.perf_counter())
                    marker = "WICKET" if record["event"] == "wicket" else "boundary"
                    print(
                        f"  [{record['iso']}Z] {marker}: {label} "
                        f"{record.get('runs')}/{record.get('wickets', '-')} "
                        f"@ {record.get('overs')} ov"
                    )

                tracked[match_id] = ratchet(previous, current)

            if verbose and poll_count % 10 == 0:
                print(
                    f"[poll {poll_count}] {len(matches)} matches, "
                    f"{len(tracked)} tracked, {fail_count} failures, "
                    f"fetch {fetch_ms:.0f}ms"
                )

            elapsed = time.perf_counter() - cycle_start
            time.sleep(max(0.0, interval - elapsed))


def main():
    parser = argparse.ArgumentParser(
        description="Record timestamped cricket scoring events from Cricbuzz."
    )
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--out", type=Path, default=Path("data/cricket_events.jsonl"))
    parser.add_argument("--match", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        response = requests.get(LIVE_SCORES_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        matches = extract_matches(response.text)
        print(f"{len(matches)} matches\n")
        for match_id, match in matches.items():
            info = match["matchInfo"]
            snaps = innings_snapshots(match)
            scores = " | ".join(
                f"{v['runs']}/{v['wickets']} ({v['overs']} ov)" for v in snaps.values()
            )
            print(f"  {match_id}  {describe(match):<40} {info.get('state', ''):<12} {scores}")
        return

    try:
        run(args.interval, args.out, args.match, args.verbose)
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    sys.exit(main())
