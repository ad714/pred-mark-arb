import argparse
import json
import statistics
from pathlib import Path

BENIGN = {"none", "all", "over-break", "udrs", "team_fifty", "team_hundred"}
RUN_WORDS = {"none", "one", "two", "three", "four", "five", "six", "byes", "leg-byes"}


def load(path, predicate=None):
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
            if predicate is None or predicate(row):
                rows.append(row)
    return rows


def is_wicket(ball, wicket_tokens):
    flags = {str(e).lower() for e in (ball.get("event") or [])}
    if wicket_tokens:
        return bool(flags & wicket_tokens)
    unknown = flags - BENIGN - RUN_WORDS
    return bool(unknown)


def price_at(quotes, t_ms, max_stale_s=120):
    best = None
    for q in quotes:
        if q["recv_ms"] <= t_ms:
            best = q
        else:
            break
    if best is None:
        return None
    if (t_ms - best["recv_ms"]) / 1000.0 > max_stale_s:
        return None
    return best["mid"]


def window_median(quotes, t_ms, lo_s, hi_s):
    vals = [
        q["mid"]
        for q in quotes
        if lo_s * 1000 <= q["recv_ms"] - t_ms <= hi_s * 1000 and q.get("mid") is not None
    ]
    return statistics.median(vals) if vals else None


def first_cross(quotes, t_ms, level, rising, lo_s, hi_s):
    for q in quotes:
        offset = (q["recv_ms"] - t_ms) / 1000.0
        if offset < lo_s or offset > hi_s or q.get("mid") is None:
            continue
        if (rising and q["mid"] >= level) or (not rising and q["mid"] <= level):
            return offset
    return None


def ball_gap_flat(quotes, t_ms, prior_s):
    """How much did price move in the prior_s before this ball? (drift measure)"""
    start = price_at(quotes, t_ms - prior_s * 1000)
    end = price_at(quotes, t_ms - 3000)
    if start is None or end is None:
        return None
    return end - start


def analyse(wickets, quotes, threshold, prior_s, post_s):
    results = []
    for ball in wickets:
        t = ball["cb_ms"]
        pre = price_at(quotes, t)
        post = price_at(quotes, t + post_s * 1000)
        if pre is None:
            results.append({"ball": ball, "skip": "no price within 120s before ball"})
            continue
        if post is None:
            results.append({"ball": ball, "skip": "recording ended before +window"})
            continue

        reaction = post - pre
        drift = ball_gap_flat(quotes, t, prior_s)
        level = pre + reaction / 2.0
        lead_lag = None
        if abs(reaction) >= threshold:
            lead_lag = first_cross(quotes, t, level, reaction > 0, -prior_s, post_s)

        results.append(
            {
                "ball": ball,
                "pre": pre,
                "post": post,
                "reaction": reaction,
                "drift": drift,
                "lead_lag": lead_lag,
            }
        )
    return results


def report(results, threshold):
    clean = [r for r in results if r.get("lead_lag") is not None]
    print(f"wicket balls found : {len(results)}")
    print(f"measurable moves   : {len(clean)}")
    print(f"reaction threshold : {threshold:.3f}\n")

    for r in results:
        ball = r["ball"]
        who = f"{ball.get('over_ball')} {ball.get('batsman','?')}"
        if r.get("skip"):
            print(f"  {ball['iso']}  {who:<28} -- {r['skip']}")
            continue

        drift = r["drift"]
        drift_s = f"{drift:+.3f}" if drift is not None else "  n/a"
        if abs(r["reaction"]) < threshold:
            print(
                f"  {ball['iso']}  {who:<28} pre {r['pre']:.3f} "
                f"reaction {r['reaction']:+.3f} (below threshold)  prior-drift {drift_s}"
            )
            continue

        direction = "POLY LED" if r["lead_lag"] < 0 else "poly lagged"
        clean_flag = ""
        if drift is not None and abs(drift) < abs(r["reaction"]) / 2:
            clean_flag = "  [CLEAN: flat before, stepped on ball]"
        print(
            f"  {ball['iso']}  {who:<28} {r['pre']:.3f}->{r['post']:.3f} "
            f"reaction {r['reaction']:+.3f}  {direction} {abs(r['lead_lag']):.0f}s  "
            f"prior-drift {drift_s}{clean_flag}"
        )

    if clean:
        offsets = [r["lead_lag"] for r in clean]
        print(f"\nlead/lag (neg = Polymarket moved before Cricbuzz published the ball):")
        print(f"  n {len(offsets)}  median {statistics.median(offsets):+.1f}s  "
              f"range {min(offsets):+.0f}..{max(offsets):+.0f}s  "
              f"poly-led {sum(1 for o in offsets if o<0)}/{len(offsets)}")


def main():
    parser = argparse.ArgumentParser(
        description="Align ball-by-ball commentary against Polymarket price moves."
    )
    parser.add_argument("--commentary", type=Path, required=True)
    parser.add_argument("--poly", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.02)
    parser.add_argument("--prior", type=float, default=45.0, help="seconds before ball to measure drift")
    parser.add_argument("--post", type=float, default=45.0, help="seconds after ball to measure reaction")
    parser.add_argument(
        "--wicket-tokens",
        default="",
        help="comma-separated event tokens that mark a wicket; empty = any unknown token",
    )
    parser.add_argument("--show-all", action="store_true", help="treat every ball as an event")
    args = parser.parse_args()

    tokens = {t.strip().lower() for t in args.wicket_tokens.split(",") if t.strip()}
    quotes = sorted(
        load(args.poly, lambda r: r.get("event") == "quote" and r.get("mid") is not None),
        key=lambda q: q["recv_ms"],
    )
    if not quotes:
        raise SystemExit("no quotes in poly file")

    balls = load(args.commentary)
    if args.show_all:
        wickets = balls
    else:
        wickets = [b for b in balls if is_wicket(b, tokens)]

    if not wickets:
        print("no wicket balls detected.")
        print("distinct event tokens seen in commentary:")
        seen = {}
        for b in balls:
            for e in b.get("event") or []:
                seen[e] = seen.get(e, 0) + 1
        for tok, n in sorted(seen.items(), key=lambda kv: -kv[1]):
            print(f"  {tok:<14} x{n}")
        return

    report(analyse(wickets, quotes, args.threshold, args.prior, args.post), args.threshold)


if __name__ == "__main__":
    main()
