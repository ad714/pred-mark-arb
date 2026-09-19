import sys
from pathlib import Path

LIVE_EDGE = Path(__file__).resolve().parent.parent / "live-edge"
sys.path.insert(0, str(LIVE_EDGE))

import requests
import dns_bypass
from record_cricket import extract_matches, HEADERS, LIVE_SCORES_URL

dns_bypass.install()
ok = True

try:
    html = requests.get(LIVE_SCORES_URL, headers=HEADERS, timeout=25).text
    matches = extract_matches(html)
    live = [m for m in matches.values()
            if m["matchInfo"].get("state") in ("In Progress", "Innings Break")]
    print(f"  cricbuzz                  OK      {len(matches)} matches, {len(live)} in progress")
except Exception as exc:
    ok = False
    print(f"  cricbuzz                  FAILED  {type(exc).__name__}: {exc}")

for url in ("https://gamma-api.polymarket.com/events?limit=1&closed=false&tag_slug=cricket",
            "https://data-api.polymarket.com/trades?limit=1",
            "https://clob.polymarket.com/markets?next_cursor="):
    host = url.split("/")[2]
    try:
        r = requests.get(url, timeout=20)
        print(f"  {host:<24}  OK      HTTP {r.status_code}, {len(r.content)} bytes")
        if r.status_code >= 400:
            ok = False
    except Exception as exc:
        ok = False
        print(f"  {host:<24}  FAILED  {type(exc).__name__}")

sys.exit(0 if ok else 1)
