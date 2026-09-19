import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from Crypto.Hash import keccak

SEARCH_API = "https://app.seer.pm/.netlify/functions/markets-search"
GNOSIS_RPC = "https://rpc.gnosischain.com"
LENS_QUOTER = "0x82150d38288e53AfcF20a5eEee47682c5Ef796d8"
SDAI = "0xaf204776c7245bf4147c2612bf6e5972ee483701"
RAW_CACHE = Path("data/raw/seer_markets_raw.json")

_digest = keccak.new(digest_bits=256)
_digest.update(b"buildBestSwap(address,bool,address,address,uint256,uint256,"
               b"uint256,uint24,int24,address)")
BUILD_BEST_SWAP = "0x" + _digest.hexdigest()[:8]


class SeerUnreachable(RuntimeError):
    pass


def _page(session, number):
    for _ in range(3):
        try:
            response = session.post(SEARCH_API, json={"page": number}, timeout=90)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            time.sleep(1.0)
    return {}


def fetch_all_markets(quiet=False):
    session = requests.Session()
    first = _page(session, 1)
    if not first:
        raise SeerUnreachable("Could not reach app.seer.pm markets-search.")

    pages = first.get("pages") or 1
    markets = list(first.get("markets") or [])
    if pages > 1:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for result in pool.map(lambda n: _page(session, n), range(2, pages + 1)):
                markets.extend(result.get("markets") or [])

    seen, unique = set(), []
    for market in markets:
        key = (market.get("chainId"), market.get("id"))
        if key not in seen:
            seen.add(key)
            unique.append(market)

    if not quiet:
        print(f"Fetched {len(unique)} Seer markets across {pages} pages")
    return unique


def tradeable(markets):
    return [m for m in markets
            if not m.get("payoutReported")
            and m.get("hasLiquidity")
            and m.get("type") == "Generic"
            and not m.get("hasAnswers")]


def _pad_address(value):
    return value.lower().replace("0x", "").rjust(64, "0")


def _pad_uint(value):
    return format(int(value), "064x")


def quote_buy(token, usd, session=None, rpc=GNOSIS_RPC):
    session = session or requests.Session()
    payload = (BUILD_BEST_SWAP
               + _pad_address("0x" + "0" * 39 + "1")
               + _pad_uint(0)
               + _pad_address(SDAI)
               + _pad_address(token)
               + _pad_uint(usd * 1e18)
               + _pad_uint(100)
               + _pad_uint(time.time() + 3600)
               + _pad_uint(0) + _pad_uint(0)
               + _pad_address("0x" + "0" * 40))
    response = session.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                                       "params": [{"to": LENS_QUOTER, "data": payload},
                                                  "latest"]}, timeout=45).json()
    result = response.get("result")
    if not result or len(result) < 258:
        return None
    shares = int(result[2 + 3 * 64: 2 + 4 * 64], 16) / 1e18
    return {"shares": shares, "avg": usd / shares} if shares > 0 else None


def save_raw(markets):
    RAW_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_CACHE, "w", encoding="utf-8") as handle:
        json.dump(markets, handle)


def load_raw():
    with open(RAW_CACHE, encoding="utf-8") as handle:
        return json.load(handle)
