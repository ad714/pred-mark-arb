#!/usr/bin/env bash
set -euo pipefail

APP=/opt/predmark
USR=predmark

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv ca-certificates tzdata
timedatectl set-timezone Asia/Kolkata 2>/dev/null || true

mkdir -p "$APP"
tar -xzf /tmp/predmark.tar.gz -C "$APP"
mkdir -p "$APP/results/paper" "$APP/results/basket"

id -u "$USR" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$APP" "$USR"

[ -x "$APP/venv/bin/python" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q requests

chmod +x "$APP/deploy/basket_scan.sh"
chown -R "$USR":"$USR" "$APP"


echo "--- preflight: can this box reach both feeds? ---"
sudo -u "$USR" "$APP/venv/bin/python" "$APP/deploy/preflight.py" || true
echo

cat > /etc/systemd/system/livedge-paper.service <<'UNIT'
[Unit]
Description=live-edge cricket paper trader
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=predmark
WorkingDirectory=/opt/predmark/live-edge
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/predmark/venv/bin/python -u paper_trade.py \
  --out /opt/predmark/results/paper \
  --bankroll 5 --stake 1 --hold 60 \
  --min-price 0.25 --max-price 0.75 --max-detect-lag 60
Restart=always
RestartSec=15
StandardOutput=append:/opt/predmark/results/paper/console.log
StandardError=append:/opt/predmark/results/paper/console.log

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/basket-scan.service <<'UNIT'
[Unit]
Description=Polymarket basket arb scan
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=predmark
WorkingDirectory=/opt/predmark/market-scanner
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/predmark/deploy/basket_scan.sh
StandardOutput=append:/opt/predmark/results/basket/console.log
StandardError=append:/opt/predmark/results/basket/console.log
UNIT

cat > /etc/systemd/system/basket-scan.timer <<'UNIT'
[Unit]
Description=Run the basket arb scan every 6 hours

[Timer]
OnBootSec=3min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now livedge-paper.service
systemctl enable --now basket-scan.timer

sleep 3
systemctl --no-pager --lines=0 status livedge-paper.service || true
echo
echo "bootstrap done. logs: $APP/results/paper/console.log"
