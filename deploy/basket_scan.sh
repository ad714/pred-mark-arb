#!/usr/bin/env bash
set -euo pipefail

cd /opt/predmark/market-scanner
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

echo "=== basket scan $STAMP ==="
/opt/predmark/venv/bin/python -m src.basket.run --min-net 1 --top 40
cp data/derived/basket.json "/opt/predmark/results/basket/basket_$STAMP.json"
