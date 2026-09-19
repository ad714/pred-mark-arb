import json
import statistics
import sys
from pathlib import Path

paths = [Path(p) for p in sys.argv[1:]] or [Path("cloud-results/paper/paper_trades.jsonl")]
rows = []
for path in paths:
    if not path.exists():
        continue
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

if not rows:
    print("no trade records found in: " + ", ".join(str(p) for p in paths))
    raise SystemExit

lags = sorted((r["recv_ms"] - r["cb_ms"]) / 1000.0
              for r in rows
              if r.get("cb_ms") and r.get("recv_ms") and r["type"] in ("open", "skip"))
closes = [r for r in rows if r["type"] == "close"]
skips = {}
for r in rows:
    if r["type"] == "skip":
        skips[r["reason"].split("(")[0].strip()] = skips.get(r["reason"].split("(")[0].strip(), 0) + 1

print(f"wickets seen on paired matches : {len(lags)}")
if lags:
    def pct(p):
        return lags[min(len(lags) - 1, int(len(lags) * p))]
    print(f"detect lag seconds             : min {lags[0]:.1f}  median {statistics.median(lags):.1f}  "
          f"p90 {pct(0.9):.1f}  max {lags[-1]:.1f}")
    print()
    print("  decision rule from notes.md: if publish lag is consistently 20-30s the edge is")
    print(f"  dead, because Polymarket repriced in ~15s. Median here is {statistics.median(lags):.1f}s.")
print()
print(f"trades closed                  : {len(closes)}")
if closes:
    wins = sum(1 for c in closes if c["pnl"] > 0)
    print(f"wins                           : {wins}/{len(closes)}")
    print(f"realized pnl                   : {sum(c['pnl'] for c in closes):+.4f}")
    moves = [c["exit_buy_mid"] - c["entry_buy_mid"] for c in closes
             if c.get("exit_buy_mid") is not None and c.get("entry_buy_mid") is not None]
    if moves:
        print(f"median mid move over hold      : {statistics.median(moves):+.4f}  (spread costs ~0.03)")
for reason, n in sorted(skips.items(), key=lambda x: -x[1]):
    print(f"  skipped: {reason:<40} {n}")
