#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:?usage: push.sh user@host [ssh-port]}"
PORT="${2:-22}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

tar --force-local -czf "$TMP/predmark.tar.gz" -C "$ROOT" \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='data' \
  live-edge market-scanner/src market-scanner/requirements.txt deploy

echo "payload: $(du -h "$TMP/predmark.tar.gz" | cut -f1)"
scp -P "$PORT" "$TMP/predmark.tar.gz" "$TARGET:/tmp/predmark.tar.gz"
ssh -p "$PORT" "$TARGET" \
  'if [ "$(id -u)" -eq 0 ]; then bash -s; else sudo bash -s; fi' \
  < "$ROOT/deploy/bootstrap.sh"
