#!/usr/bin/env bash
set -uo pipefail

INTERVAL=${INTERVAL:-1200}
DEADLINE=${DEADLINE:-19800}
OUT=docs/data/football.jsonl

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

summarise() {
  python - "$1" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, "deploy")
import build_dashboard

view = build_dashboard.football_view()
(build_dashboard.DATA / "football.json").write_text(
    json.dumps(view, indent=1), encoding="utf-8")

latest = view.get("latest") or {}
line = "| {} | {} | {} | {} | {} |".format(
    sys.argv[1], latest.get("markets", 0), latest.get("fixtures", 0),
    latest.get("in_band", 0), latest.get("tradeable", 0))
print(line)

summary = Path(__import__("os").environ.get("GITHUB_STEP_SUMMARY", ""))
if str(summary):
    header = "" if summary.exists() and summary.stat().st_size else (
        "| cycle | markets | fixtures | in band | tradeable |\n"
        "| --- | --- | --- | --- | --- |\n")
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write(header + line + "\n")
PY
}

publish() {
  for attempt in 1 2 3 4 5; do
    git fetch -q origin main
    git reset -q --soft origin/main
    git add docs/data/football.jsonl docs/data/football.json
    if git diff --cached --quiet; then
      echo "no change to publish"
      return 0
    fi
    git commit -q -m "chore: football band sample"
    if git push -q origin HEAD:main; then
      echo "published on attempt $attempt"
      return 0
    fi
    echo "push raced, retrying"
    sleep $((attempt * 4))
  done
  return 1
}

started=$SECONDS
cycle=0

while :; do
  cycle=$((cycle + 1))
  echo "::group::cycle $cycle at $(date -u +%H:%M:%SZ)"
  python deploy/football_scan.py "$OUT" || echo "scan failed, carrying on"
  summarise "$cycle" || echo "summary failed, carrying on"
  publish || echo "publish failed, carrying on"
  echo "::endgroup::"

  elapsed=$((SECONDS - started))
  left=$((DEADLINE - elapsed))
  if [ "$left" -lt "$INTERVAL" ]; then
    echo "stopping after $cycle cycles, ${elapsed}s elapsed"
    break
  fi
  echo "sleeping ${INTERVAL}s, ${left}s of budget left"
  sleep "$INTERVAL"
done
