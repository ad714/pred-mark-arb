import argparse
import json
import statistics
from pathlib import Path


def load(path, event_types=None):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event_types and row.get("event") not in event_types:
                continue
            rows.append(row)
    return rows


def cricket_time(row):
    return row["wall_ms"] / 1000.0


def poly_time(row):
    return row["recv_ms"] / 1000.0


def baseline_mid(quotes, t_event, lookback_start, lookback_end):
    window = [
        q["mid"]
        for q in quotes
        if lookback_start <= poly_time(q) - t_event <= lookback_end and q.get("mid") is not None
    ]
    return statistics.median(window) if window else None


def window_median(quotes, t_event, lo, hi):
    vals = [
        q["mid"]
        for q in quotes
        if lo <= poly_time(q) - t_event <= hi and q.get("mid") is not None
    ]
    return statistics.median(vals) if vals else None


def crossing_offset(quotes, t_event, level, rising, lo, hi):
    for q in sorted(quotes, key=poly_time):
        offset = poly_time(q) - t_event
        if offset < lo or offset > hi or q.get("mid") is None:
            continue
        if (rising and q["mid"] >= level) or (not rising and q["mid"] <= level):
            return offset
    return None


def extreme_and_revert(quotes, t_event, base, window_end):
    after = [
        q
        for q in quotes
        if 0 <= poly_time(q) - t_event <= window_end and q.get("mid") is not None
    ]
    if not after:
        return None, None, None

    peak = max(after, key=lambda q: abs(q["mid"] - base))
    peak_offset = poly_time(peak) - t_event
    settled = [q for q in after if poly_time(q) - t_event > peak_offset]
    final = settled[-1]["mid"] if settled else peak["mid"]
    return peak["mid"], peak_offset, final


def analyse(cricket_rows, quotes, threshold, pre_window, post_window, event_filter):
    results = []
    for row in cricket_rows:
        if event_filter and row.get("event") != event_filter:
            continue

        t_event = cricket_time(row)
        early = window_median(quotes, t_event, -120.0, -60.0)
        just_before = window_median(quotes, t_event, -20.0, -3.0)
        after = window_median(quotes, t_event, 20.0, 90.0)

        if early is None or just_before is None or after is None:
            results.append({"row": row, "skipped": "insufficient quote coverage"})
            continue

        total = after - early
        drift = just_before - early
        reaction = after - just_before

        if abs(total) < threshold:
            results.append(
                {"row": row, "skipped": f"no net move (|{total:+.3f}| < {threshold:.3f})"}
            )
            continue

        trend_dominates = abs(drift) > abs(reaction)
        level = early + total / 2.0
        offset = crossing_offset(
            quotes, t_event, level, total > 0, pre_window, post_window
        )
        peak, peak_offset, final = extreme_and_revert(
            quotes, t_event, just_before, post_window
        )

        results.append(
            {
                "row": row,
                "early": early,
                "just_before": just_before,
                "after": after,
                "total": total,
                "drift": drift,
                "reaction": reaction,
                "trend_dominates": trend_dominates,
                "lead_lag": offset,
                "peak": peak,
                "peak_offset": peak_offset,
                "final": final,
            }
        )
    return results


def report(results, threshold, outcome):
    usable = [
        r
        for r in results
        if r.get("lead_lag") is not None and not r.get("trend_dominates")
    ]
    flagged = [r for r in results if r.get("trend_dominates")]

    print(f"quote outcome tracked : {outcome}")
    print(f"move threshold        : {threshold:.3f}")
    print(f"events examined       : {len(results)}")
    print(f"usable (trend small)  : {len(usable)}")
    print(f"discarded (trend big) : {len(flagged)}\n")

    for result in results:
        row = result["row"]
        label = f"{row.get('event','?'):<8} {row.get('runs')}/{row.get('wickets')} @ {row.get('overs')}"
        stamp = row.get("iso", "")[-8:]

        if result.get("skipped"):
            print(f"  {stamp}  {label}  -- {result['skipped']}")
            continue

        detail = (
            f"drift {result['drift']:+.3f} / reaction {result['reaction']:+.3f}"
        )
        if result["trend_dominates"]:
            print(f"  {stamp}  {label}  UNRELIABLE: pre-event drift exceeds reaction  ({detail})")
            continue

        if result["lead_lag"] is None:
            print(f"  {stamp}  {label}  net {result['total']:+.3f} but no 50% crossing  ({detail})")
            continue

        direction = "POLY LED" if result["lead_lag"] < 0 else "poly lagged"
        line = (
            f"  {stamp}  {label}  {result['early']:.3f} -> {result['after']:.3f}  "
            f"{direction} by {abs(result['lead_lag']):.0f}s  ({detail})"
        )
        if result["peak"] is not None and result["final"] is not None:
            reverted = abs(result["peak"] - result["final"])
            line += f"  | peak {result['peak']:.3f} revert {reverted:.3f}"
        print(line)

    if not usable:
        print(
            "\nnothing usable. every event was swamped by pre-existing price drift,\n"
            "which is what happens in one-sided matches. need close matches where the\n"
            "event impact is larger than the background trend."
        )
        return

    offsets = [r["lead_lag"] for r in usable]
    led = [o for o in offsets if o < 0]
    print("\nlead/lag seconds (negative = Polymarket moved first):")
    print(f"  n       : {len(offsets)}")
    print(f"  median  : {statistics.median(offsets):+.1f}s")
    print(f"  min/max : {min(offsets):+.1f}s / {max(offsets):+.1f}s")
    print(f"  poly led: {len(led)}/{len(offsets)}")

    reverts = [
        abs(r["peak"] - r["final"])
        for r in usable
        if r.get("peak") is not None and r.get("final") is not None
    ]
    if reverts:
        print(f"\novershoot reverted (cents): median {statistics.median(reverts)*100:.1f}c")


def main():
    parser = argparse.ArgumentParser(
        description="Align cricket scoring events against Polymarket price moves."
    )
    parser.add_argument("--cricket", type=Path, required=True)
    parser.add_argument("--poly", type=Path, required=True)
    parser.add_argument("--match", default=None, help="substring filter on cricket match label")
    parser.add_argument("--event", default="wicket", help="wicket, boundary, or all")
    parser.add_argument("--threshold", type=float, default=0.02)
    parser.add_argument("--pre", type=float, default=-120.0)
    parser.add_argument("--post", type=float, default=120.0)
    args = parser.parse_args()

    cricket_rows = load(args.cricket)
    if args.match:
        cricket_rows = [r for r in cricket_rows if args.match.lower() in (r.get("match") or "").lower()]

    quotes = load(args.poly, event_types={"quote"})
    if not quotes:
        raise SystemExit("no quote rows in poly file")

    outcome = quotes[0].get("outcome", "?")
    event_filter = None if args.event == "all" else args.event

    results = analyse(cricket_rows, quotes, args.threshold, args.pre, args.post, event_filter)
    report(results, args.threshold, outcome)


if __name__ == "__main__":
    main()
