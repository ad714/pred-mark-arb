import json
from pathlib import Path

import requests

GAMMA_MARKETS_API = "https://gamma-api.polymarket.com/markets"
PAGE_LIMIT = 500
RAW_CACHE = Path("data/raw/poly_screen_raw.json")


class PolymarketUnreachable(RuntimeError):
    pass


def fetch_active_markets(max_markets=3000):
    markets = []
    offset = 0

    while len(markets) < max_markets:
        params = {
            "active": "true",
            "closed": "false",
            "archived": "false",
            "limit": PAGE_LIMIT,
            "offset": offset,
            "order": "volumeNum",
            "ascending": "false",
        }

        try:
            response = requests.get(GAMMA_MARKETS_API, params=params, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise PolymarketUnreachable(
                "Could not reach gamma-api.polymarket.com.\n"
                "Your DNS is most likely blocking Polymarket. Connect a VPN or switch "
                "DNS, then re-run. To score a previously saved snapshot instead, run "
                "with --offline."
            ) from exc

        response.raise_for_status()
        page = response.json()

        if not isinstance(page, list) or not page:
            break

        markets.extend(page)
        print(f"Fetched {len(page)} markets (total {len(markets)})")

        if len(page) < PAGE_LIMIT:
            break

        offset += PAGE_LIMIT

    return markets[:max_markets]


def save_raw(markets):
    RAW_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_CACHE, "w", encoding="utf-8") as handle:
        json.dump(markets, handle)


def load_raw():
    if not RAW_CACHE.exists():
        raise PolymarketUnreachable(
            f"No cached snapshot at {RAW_CACHE}. Run once online to create one."
        )
    with open(RAW_CACHE, "r", encoding="utf-8") as handle:
        return json.load(handle)
