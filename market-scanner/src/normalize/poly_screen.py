import json
from datetime import datetime, timezone


def _num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _first(raw, *names):
    for name in names:
        value = raw.get(name)
        if value not in (None, ""):
            return value
    return None


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_field(raw, key):
    events = raw.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        return events[0].get(key)
    return None


def normalize_screen_market(raw, now=None):
    now = now or datetime.now(timezone.utc)

    outcomes = [str(o) for o in _json_list(_first(raw, "outcomes"))]
    prices = [p for p in (_num(x) for x in _json_list(_first(raw, "outcomePrices"))) if p is not None]

    favorite_price = max(prices) if prices else None
    favorite_outcome = None
    if favorite_price is not None and len(outcomes) == len(prices):
        favorite_outcome = outcomes[prices.index(favorite_price)]

    best_bid = _num(_first(raw, "bestBid"))
    best_ask = _num(_first(raw, "bestAsk"))

    spread = _num(_first(raw, "spread"))
    if spread is None and best_bid is not None and best_ask is not None:
        spread = best_ask - best_bid
    spread_cents = round(spread * 100, 2) if spread is not None else None

    end_dt = _parse_dt(_first(raw, "endDate", "endDateIso", "end_date_iso"))
    days_left = (end_dt - now).total_seconds() / 86400 if end_dt else None

    slug = _event_field(raw, "slug") or _first(raw, "slug", "market_slug")

    return {
        "id": str(_first(raw, "id", "conditionId", "condition_id") or ""),
        "question": _first(raw, "question", "title") or "",
        "event_title": _event_field(raw, "title") or "",
        "url": f"https://polymarket.com/event/{slug}" if slug else "",
        "outcomes": outcomes,
        "prices": prices,
        "favorite_outcome": favorite_outcome,
        "favorite_price": favorite_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread_cents": spread_cents,
        "liquidity": _num(_first(raw, "liquidityNum", "liquidity"), 0.0),
        "volume": _num(_first(raw, "volumeNum", "volume"), 0.0),
        "volume_24h": _num(_first(raw, "volume24hr", "volume24hrClob"), 0.0),
        "end_date": end_dt.isoformat() if end_dt else None,
        "days_left": days_left,
        "accepting_orders": bool(_first(raw, "acceptingOrders", "accepting_orders")),
        "order_book": bool(_first(raw, "enableOrderBook", "enable_order_book")),
        "closed": bool(raw.get("closed")),
        "archived": bool(raw.get("archived")),
        "restricted": bool(raw.get("restricted")),
        "neg_risk": bool(_first(raw, "negRisk", "neg_risk")),
        "description": _first(raw, "description") or "",
        "resolution_source": _first(raw, "resolutionSource", "resolution_source") or "",
        "uma_status": _first(raw, "umaResolutionStatus") or "",
        "min_order_size": _num(_first(raw, "orderMinSize", "minimum_order_size"), 0.0),
    }
