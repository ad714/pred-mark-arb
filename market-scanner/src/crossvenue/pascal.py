"""Pascal market data.

Pascal publishes the Polymarket condition_id and outcome token id that each of its
markets mirrors, and its own rules say it settles to whichever outcome wins the
referenced Polymarket market. The two venues therefore join exactly and read the
same oracle, which is the whole reason this venue is worth watching.

Every fetch here reports how many batches failed. A book that could not be read is
not a book that fails to cross, and the two must never look the same downstream.
"""

import requests

MARKETS = "https://data.pascal.trade/api/v1/markets"
BOOKS = "https://data.pascal.trade/api/v1/books"
POLY_BOOKS = "https://clob.polymarket.com/books"
GAMMA = "https://gamma-api.polymarket.com/markets"

SYMBOL_BATCH = 40
TOKEN_BATCH = 100
SLUG_BATCH = 100
DEFAULT_POLY_FEE = 0.04


def fetch_markets():
    """Every Pascal market that names a Polymarket outcome token."""
    out = []
    for market in requests.get(MARKETS, timeout=90).json()["data"]:
        attributes = market.get("display_attributes") or {}
        reference = attributes.get("reference") or {}
        token = reference.get("market_outcome_token_id")
        if reference.get("kind") != "polymarket" or not token:
            continue
        out.append({
            "symbol": market["symbol"],
            "token": token,
            "slug": reference.get("market_slug"),
            "condition_id": reference.get("condition_id"),
            "event": attributes.get("event_description"),
            "outcome": attributes.get("market_description"),
            "resolves_ms": attributes.get("expected_resolution_time_ms"),
            "taker_fee": float(market["taker_fee_rate"]),
            "open_interest": float(market.get("open_interest") or 0),
        })
    return out


def fetch_books(symbols, session=None):
    """Pascal books, plus the number of batches that could not be read."""
    session = session or requests.Session()
    books, failed = {}, 0
    for start in range(0, len(symbols), SYMBOL_BATCH):
        batch = symbols[start:start + SYMBOL_BATCH]
        try:
            response = session.get(BOOKS, params={"symbols": ",".join(batch)},
                                   timeout=60)
            if response.status_code == 200:
                books.update(response.json()["data"]["books"])
            else:
                failed += len(batch)
        except (requests.RequestException, ValueError, KeyError):
            failed += len(batch)
    return books, failed


def fetch_poly_books(tokens, session=None):
    """Polymarket books, plus the number of tokens in batches that failed."""
    session = session or requests.Session()
    books, failed = {}, 0
    for start in range(0, len(tokens), TOKEN_BATCH):
        batch = tokens[start:start + TOKEN_BATCH]
        try:
            response = session.post(POLY_BOOKS, json=[{"token_id": t} for t in batch],
                                    timeout=60)
            if response.status_code != 200:
                failed += len(batch)
                continue
            for book in response.json():
                books[book["asset_id"]] = book
        except (requests.RequestException, ValueError, KeyError):
            failed += len(batch)
    return books, failed


def fetch_poly_fees(slugs, session=None):
    """Polymarket's own taker rate and exponent per market slug, from feeSchedule.

    The `fee` field is null on these markets; the live rate is in feeSchedule and
    is charged taker-only. A rate of exactly zero is real - Polymarket runs some
    categories fee-free - so it is read as zero rather than defaulted away. Only a
    missing schedule falls back, and it falls back to the 4% the referenced set
    uses, so a lookup miss never flatters an edge.
    """
    session = session or requests.Session()
    fees = {}
    unique = sorted({s for s in slugs if s})
    for start in range(0, len(unique), SLUG_BATCH):
        batch = unique[start:start + SLUG_BATCH]
        try:
            response = session.get(
                GAMMA,
                params=[("slug", s) for s in batch] + [("limit", SLUG_BATCH)],
                timeout=60)
            if response.status_code != 200:
                continue
            for market in response.json():
                schedule = market.get("feeSchedule") or {}
                rate = schedule.get("rate")
                exponent = schedule.get("exponent")
                fees[market.get("slug")] = (
                    DEFAULT_POLY_FEE if rate is None else float(rate),
                    1 if exponent is None else int(exponent),
                )
        except (requests.RequestException, ValueError, KeyError):
            continue
    return fees
