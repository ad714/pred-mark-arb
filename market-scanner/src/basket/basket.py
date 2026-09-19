import json
import re
from datetime import datetime, timezone

PLACEHOLDER = re.compile(
    r"^(other|other / unconfirmed.*|another .*|[a-z]|\d{1,2}|"
    r"(?:party|person|candidate|player|driver|team|option|choice|horse|fighter|entrant|"
    r"contestant|nominee|runner|athlete|competitor|club|school|company|city)"
    r"\s+[a-z0-9]{1,2})$",
    re.IGNORECASE,
)

MAX_BREAKPOINTS = 120
DEAD_ASK = 0.999


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


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def yes_slot(market):
    outcomes = [str(o) for o in _json_list(market.get("outcomes"))]
    for index, outcome in enumerate(outcomes):
        if outcome.strip().lower() == "yes":
            return index
    return None


def yes_token(market):
    index = yes_slot(market)
    tokens = [str(t) for t in _json_list(market.get("clobTokenIds"))]
    if index is None or index >= len(tokens):
        return None
    return tokens[index]


def yes_mark(market):
    if (_num(market.get("volumeNum"), 0.0) or 0.0) > 0:
        index = yes_slot(market)
        prices = [_num(x) for x in _json_list(market.get("outcomePrices"))]
        if index is not None and index < len(prices) and prices[index] is not None:
            return prices[index], True
        last = _num(market.get("lastTradePrice"))
        if last is not None:
            return last, True
    bid = _num(market.get("bestBid"))
    if bid is not None and bid > 0:
        return bid, True
    return 0.0, False


def fee_terms(market):
    if not market.get("feesEnabled"):
        return 0.0, 1.0
    schedule = market.get("feeSchedule") or {}
    rate = _num(schedule.get("rate"), 0.0) or 0.0
    exponent = _num(schedule.get("exponent"), 1.0) or 1.0
    return rate, exponent


def event_legs(event):
    legs = []
    for market in event.get("markets") or []:
        token = yes_token(market)
        if not token:
            continue
        rate, exponent = fee_terms(market)
        mark, mark_known = yes_mark(market)
        tradeable = bool(
            market.get("active")
            and market.get("acceptingOrders")
            and market.get("enableOrderBook")
            and not market.get("closed")
            and not market.get("archived")
        )
        legs.append(
            {
                "name": market.get("groupItemTitle") or market.get("question") or "",
                "token": token,
                "best_ask": _num(market.get("bestAsk")),
                "mark": mark,
                "mark_known": mark_known,
                "tradeable": tradeable,
                "fee_rate": rate,
                "fee_exponent": exponent,
            }
        )
    return legs


def quoted_sum(legs):
    total = 0.0
    quoted = 0
    dark = 0
    for leg in legs:
        ask = leg["best_ask"]
        if not leg["tradeable"] or ask is None or ask <= 0 or ask >= DEAD_ASK:
            dark += 1
            continue
        total += ask
        quoted += 1
    return total, quoted, dark


def walk_leg(asks, size, rate, exponent):
    need = size
    cost = 0.0
    fee = 0.0
    for price, available in asks:
        take = available if available < need else need
        cost += take * price
        if rate:
            fee += take * rate * (price * (1.0 - price)) ** exponent
        need -= take
        if need <= 1e-9:
            return cost, fee
    return None, None


def _depth(asks):
    return sum(size for _, size in asks)


def _sizes(legs):
    cap = min(_depth(leg["asks"]) for leg in legs)
    points = set()
    for leg in legs:
        running = 0.0
        for _, size in leg["asks"]:
            running += size
            if running <= cap:
                points.add(round(running, 4))
    points.add(round(cap, 4))
    points = sorted(point for point in points if point > 0)
    if len(points) > MAX_BREAKPOINTS:
        step = len(points) / float(MAX_BREAKPOINTS)
        keep = {points[int(index * step)] for index in range(MAX_BREAKPOINTS)}
        keep.add(points[-1])
        points = sorted(keep)
    return points


def basket_curve(legs):
    if not legs:
        return []
    curve = []
    for size in _sizes(legs):
        cost = 0.0
        fee = 0.0
        for leg in legs:
            leg_cost, leg_fee = walk_leg(
                leg["asks"], size, leg["fee_rate"], leg["fee_exponent"]
            )
            if leg_cost is None:
                cost = None
                break
            cost += leg_cost
            fee += leg_fee
        if cost is None:
            continue
        curve.append(
            {
                "size": size,
                "cost": round(cost, 4),
                "fee": round(fee, 4),
                "gross": round(size - cost, 4),
                "net": round(size - cost - fee, 4),
            }
        )
    return curve


def leg_costs(legs, size):
    costs = {}
    for leg in legs:
        cost, _ = walk_leg(leg["asks"], size, leg["fee_rate"], leg["fee_exponent"])
        if cost is not None:
            costs[leg["name"]] = round(cost, 4)
    return costs


def assess_event(event, books, now=None):
    now = now or datetime.now(timezone.utc)
    legs = event_legs(event)

    buyable = []
    dark = []
    for leg in legs:
        book = books.get(leg["token"])
        if leg["tradeable"] and book and book["asks"]:
            buyable.append(dict(leg, asks=book["asks"]))
        else:
            dark.append(leg)

    if len(buyable) < 2:
        return None

    curve = basket_curve(buyable)
    if not curve:
        return None

    peak = max(curve, key=lambda row: row["net"])
    if peak["net"] <= 0:
        return None

    dark_priced = [leg for leg in dark if leg["mark_known"]]
    dark_unknown = [leg for leg in dark if not leg["mark_known"]]
    named = [leg["name"] for leg in dark_unknown
             if not PLACEHOLDER.match((leg["name"] or "").strip())]
    dark_marks = sorted((leg["mark"] or 0.0) for leg in dark_priced)
    dark_sum = sum(dark_marks)

    end = _parse_dt(event.get("endDate"))
    days_left = round((end - now).total_seconds() / 86400.0, 1) if end else None

    at_100 = next((row for row in curve if row["size"] >= 100), None)
    fee_rates = sorted({leg["fee_rate"] for leg in buyable})
    costs = leg_costs(buyable, peak["size"])
    linchpin = max(costs.items(), key=lambda item: item[1]) if costs else ("", 0.0)

    return {
        "event_id": event.get("id"),
        "title": event.get("title"),
        "slug": event.get("slug"),
        "url": f"https://polymarket.com/event/{event.get('slug')}",
        "tags": [t.get("label") for t in (event.get("tags") or []) if t.get("label")][:4],
        "days_left": days_left,
        "volume_24h": round(_num(event.get("volume24hr"), 0.0) or 0.0),
        "outcomes_total": len(legs),
        "legs_buyable": len(buyable),
        "legs_dark": len(dark),
        "dark_names": [leg["name"] for leg in dark][:12],
        "legs_unknown": len(dark_unknown),
        "legs_unknown_named": len(named),
        "unknown_named": named[:12],
        "unknown_names": [leg["name"] for leg in dark_unknown][:12],
        "dark_mark_sum": round(dark_sum, 4),
        "dark_mark_max": round(dark_marks[-1], 4) if dark_marks else 0.0,
        "complete_basket": not dark,
        "fee_rates": fee_rates,
        "peak_size": peak["size"],
        "peak_net": peak["net"],
        "peak_gross": peak["gross"],
        "peak_fee": peak["fee"],
        "peak_capital": peak["cost"],
        "peak_return_pct": round(100.0 * peak["net"] / peak["cost"], 2) if peak["cost"] else None,
        "cost_per_share_100": round(at_100["cost"] / at_100["size"], 4) if at_100 else None,
        "cost_per_share_peak": round(peak["cost"] / peak["size"], 4),
        "full_cost_per_share": round(peak["cost"] / peak["size"] + dark_sum, 4),
        "max_fillable": curve[-1]["size"],
        "linchpin": linchpin[0],
        "linchpin_cost": linchpin[1],
        "curve": curve,
        "legs": [
            {
                "name": leg["name"],
                "best_ask": leg["best_ask"],
                "depth": round(_depth(leg["asks"]), 2),
                "cost_at_peak": costs.get(leg["name"]),
                "fee_rate": leg["fee_rate"],
            }
            for leg in buyable
        ],
    }
