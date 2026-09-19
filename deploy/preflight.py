import sys
import time
from pathlib import Path

LIVE_EDGE = Path(__file__).resolve().parent.parent / "live-edge"
sys.path.insert(0, str(LIVE_EDGE))

import requests
import dns_bypass
from record_cricket import extract_matches, HEADERS, LIVE_SCORES_URL

dns_bypass.install()
ok = True
ATTEMPTS = 3


def attempt(label, call):
    global ok
    last = None
    for tries in range(ATTEMPTS):
        try:
            print(f"  {label:<24}  OK      {call()}")
            return
        except Exception as exc:
            last = exc
            if tries < ATTEMPTS - 1:
                time.sleep(3 * (tries + 1))
    ok = False
    print(f"  {label:<24}  FAILED  {type(last).__name__}: {last}")


def cricbuzz():
    matches = extract_matches(requests.get(LIVE_SCORES_URL, headers=HEADERS, timeout=25).text)
    live = [m for m in matches.values()
            if m["matchInfo"].get("state") in ("In Progress", "Innings Break")]
    return f"{len(matches)} matches, {len(live)} in progress"


attempt("cricbuzz", cricbuzz)

def probe(url):
    def run():
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return f"HTTP {r.status_code}, {len(r.content)} bytes"
    return run


for target in ("https://gamma-api.polymarket.com/events?limit=1&closed=false&tag_slug=cricket",
               "https://data-api.polymarket.com/trades?limit=1",
               "https://clob.polymarket.com/markets?next_cursor="):
    attempt(target.split("/")[2], probe(target))

sys.exit(0 if ok else 1)
