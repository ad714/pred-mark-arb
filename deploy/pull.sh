#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:?usage: pull.sh user@host [ssh-port]}"
PORT="${2:-22}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/cloud-results"
mkdir -p "$DEST"

scp -P "$PORT" -r \
  "$TARGET:/opt/predmark/results/paper" \
  "$TARGET:/opt/predmark/results/basket" \
  "$DEST/"
echo "pulled -> $DEST"

ssh -p "$PORT" "$TARGET" \
  'systemctl is-active livedge-paper.service; systemctl show livedge-paper.service -p NRestarts --value | sed "s/^/restarts: /"'

python "$ROOT/deploy/summarize.py" "$DEST/paper/paper_trades.jsonl"
