import requests

from src.fetch.poly import PolymarketUnreachable

CLOB_BOOKS_API = "https://clob.polymarket.com/books"
BATCH_SIZE = 120


def _ladder(levels, reverse):
    rungs = []
    for level in levels or []:
        try:
            price = float(level["price"])
            size = float(level["size"])
        except (KeyError, TypeError, ValueError):
            continue
        if price > 0 and size > 0:
            rungs.append((price, size))
    rungs.sort(key=lambda rung: rung[0], reverse=reverse)
    return rungs


def fetch_books(token_ids):
    books = {}
    tokens = list(dict.fromkeys(token_ids))

    for start in range(0, len(tokens), BATCH_SIZE):
        chunk = tokens[start:start + BATCH_SIZE]
        payload = [{"token_id": token} for token in chunk]

        try:
            response = requests.post(CLOB_BOOKS_API, json=payload, timeout=40)
        except requests.exceptions.ConnectionError as exc:
            raise PolymarketUnreachable(
                "Could not reach clob.polymarket.com to read order books."
            ) from exc

        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            continue

        for book in page:
            token = book.get("asset_id")
            if not token:
                continue
            books[token] = {
                "asks": _ladder(book.get("asks"), reverse=False),
                "bids": _ladder(book.get("bids"), reverse=True),
                "tick_size": book.get("tick_size"),
                "min_order_size": book.get("min_order_size"),
            }

    return books
