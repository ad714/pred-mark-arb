#!/usr/bin/env bash
# Poll the cross-venue watch for hours inside a single Actions run.
#
# A schedule is intent, not cadence: this repo's */15 publish workflow actually
# lands every 2 to 6 hours, because GitHub drops scheduled fires under load. A
# short-dated market can open and settle inside one of those gaps, so one
# triggered run keeps checking rather than checking once and exiting.
#
# Two rules the loop exists to enforce:
#   - A failed scan must not alert. No data is not the same as no hits, and the
#     previous iteration's alert.json is still sitting on disk.
#   - Publish when the alerting set CHANGES, not on every check that has a hit,
#     or a hit that persists all afternoon leaves thirty commits behind.
set -u

BUDGET_MIN=${BUDGET_MIN:-330}
INTERVAL_MIN=${INTERVAL_MIN:-3}
CAPITAL=${CAPITAL:-25}
HORIZON=${HORIZON:-7}
MIN_PROFIT=${MIN_PROFIT:-0.10}

deadline=$(( $(date -u +%s) + BUDGET_MIN * 60 ))
checks=0
scanned=0
crossed=0
previous=""

commit_history() {
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  for attempt in 1 2 3 4 5; do
    git fetch -q origin main
    git reset -q origin/main
    if ! git add docs/data/crossvenue.json docs/data/crossvenue.jsonl 2>/dev/null; then
      echo "nothing written yet, skipping publish"
      return 0
    fi
    if git diff --cached --quiet; then
      echo "no change to publish"
      return 0
    fi
    git commit -q -m "chore: crossvenue watch"
    if git push -q origin HEAD:main; then
      echo "published on attempt $attempt"
      return 0
    fi
    echo "push raced, retrying"
    sleep $(( attempt * 4 ))
  done
  return 1
}

# The symbols currently over the alert bar, sorted, as one line. Empty when the
# file is missing or unparseable, which is indistinguishable from "no hits" only
# because we never reach here unless the scan succeeded.
alert_fingerprint() {
  python - <<'PY' 2>/dev/null || true
import json
try:
    hits = json.load(open("alert.json")).get("hits") or []
except Exception:
    raise SystemExit(0)
print(" ".join(sorted(h["symbol"] for h in hits)))
PY
}

while [ "$(date -u +%s)" -lt "$deadline" ]; do
  checks=$(( checks + 1 ))
  echo "--- check $checks at $(date -u +%H:%M:%SZ) ---"

  if ( cd market-scanner && python -m src.crossvenue.run \
         --capital "$CAPITAL" --horizon-days "$HORIZON" --min-profit "$MIN_PROFIT" ); then
    scanned=$(( scanned + 1 ))
    current=$(alert_fingerprint)

    if python deploy/crossvenue_alert.py; then
      if [ -n "$current" ]; then
        crossed=$(( crossed + 1 ))
      fi
      if [ "$current" != "$previous" ]; then
        echo "alerting set changed: [${previous:-none}] -> [${current:-none}]"
        commit_history
        previous="$current"
      fi
    else
      echo "alert step failed; state left untouched, will retry next check"
    fi
  else
    echo "scan failed; not alerting on stale data"
  fi

  remaining=$(( deadline - $(date -u +%s) ))
  if [ "$remaining" -le $(( INTERVAL_MIN * 60 )) ]; then
    break
  fi
  sleep $(( INTERVAL_MIN * 60 ))
done

echo "--- $checks checks, $scanned scanned cleanly, $crossed with a crossed book ---"
commit_history

if [ "$scanned" -eq 0 ]; then
  echo "every scan in this run failed"
  exit 1
fi
