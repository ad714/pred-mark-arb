import json
from pathlib import Path

import requests

from src.fetch.poly import PolymarketUnreachable

GAMMA_EVENTS_API = "https://gamma-api.polymarket.com/events"
PAGE_LIMIT = 100
OFFSET_CAP = 2000
RAW_CACHE = Path("data/raw/poly_events_raw.json")


def fetch_active_events(max_events=2100, quiet=False):
    events = []
    offset = 0

    while len(events) < max_events and offset <= OFFSET_CAP:
        params = {
            "active": "true",
            "closed": "false",
            "archived": "false",
            "limit": PAGE_LIMIT,
            "offset": offset,
            "order": "volume24hr",
            "ascending": "false",
        }

        try:
            response = requests.get(GAMMA_EVENTS_API, params=params, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise PolymarketUnreachable(
                "Could not reach gamma-api.polymarket.com.\n"
                "This machine sinkholes Polymarket over DNS. The runner installs the "
                "DoH bypass from live-edge/dns_bypass.py; check that file is present, "
                "or re-run with --offline to score a saved snapshot."
            ) from exc

        response.raise_for_status()
        page = response.json()

        if not isinstance(page, list) or not page:
            break

        events.extend(page)
        if not quiet:
            print(f"Fetched {len(page)} events (total {len(events)})")

        if len(page) < PAGE_LIMIT:
            break

        offset += PAGE_LIMIT

    return events[:max_events]


def save_raw(events):
    RAW_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_CACHE, "w", encoding="utf-8") as handle:
        json.dump(events, handle)


def load_raw():
    if not RAW_CACHE.exists():
        raise PolymarketUnreachable(
            f"No cached snapshot at {RAW_CACHE}. Run once online to create one."
        )
    with open(RAW_CACHE, "r", encoding="utf-8") as handle:
        return json.load(handle)
