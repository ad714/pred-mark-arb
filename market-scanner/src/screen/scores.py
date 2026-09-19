import math

SPREAD_TIGHT_CENTS = 1.0
SPREAD_WIDE_CENTS = 10.0

LIQUIDITY_FLOOR = 500.0
LIQUIDITY_STRONG = 100_000.0

VOLUME_24H_FLOOR = 100.0
VOLUME_24H_STRONG = 50_000.0

MIN_LIQUIDITY_TO_SCREEN = 1_000.0

EXECUTION_WEIGHT = 0.45
RESOLUTION_WEIGHT = 0.30
TIME_WEIGHT = 0.25

SPREAD_SUB_WEIGHT = 0.45
DEPTH_SUB_WEIGHT = 0.35
ACTIVITY_SUB_WEIGHT = 0.20

TIME_BANDS = [(7, 100.0), (30, 80.0), (90, 55.0), (180, 35.0), (365, 15.0)]

FAVORITE_PRICE_MIN = 0.95

AMBIGUITY_PHRASES = [
    "at the discretion",
    "subjective",
    "consensus of",
    "credible reporting",
    "generally accepted",
    "a resolver",
    "reasonable judgment",
    "spirit of the market",
]


def _linear_scale(value, best, worst):
    if value is None:
        return 0.0
    if value <= best:
        return 100.0
    if value >= worst:
        return 0.0
    return 100.0 * (worst - value) / (worst - best)


def _log_scale(value, floor, strong):
    if value is None or value <= floor:
        return 0.0
    if value >= strong:
        return 100.0
    return 100.0 * math.log10(value / floor) / math.log10(strong / floor)


def is_screenable(market):
    if market["closed"] or market["archived"]:
        return False, "closed or archived"
    if not market["accepting_orders"]:
        return False, "not accepting orders"
    if not market["order_book"]:
        return False, "no central order book"
    if (market["liquidity"] or 0.0) < MIN_LIQUIDITY_TO_SCREEN:
        return False, f"liquidity below ${MIN_LIQUIDITY_TO_SCREEN:,.0f}"
    if market["days_left"] is None or market["days_left"] <= 0:
        return False, "no future end date"
    return True, ""


def execution_score(market):
    notes = []

    if market["spread_cents"] is None:
        notes.append("spread unknown, scored as worst case")
    elif market["spread_cents"] > SPREAD_WIDE_CENTS:
        notes.append(f"wide spread {market['spread_cents']:.1f}c")

    if (market["volume_24h"] or 0.0) < VOLUME_24H_FLOOR:
        notes.append("almost no volume in last 24h")

    spread_part = _linear_scale(market["spread_cents"], SPREAD_TIGHT_CENTS, SPREAD_WIDE_CENTS)
    depth_part = _log_scale(market["liquidity"], LIQUIDITY_FLOOR, LIQUIDITY_STRONG)
    activity_part = _log_scale(market["volume_24h"], VOLUME_24H_FLOOR, VOLUME_24H_STRONG)

    score = (
        SPREAD_SUB_WEIGHT * spread_part
        + DEPTH_SUB_WEIGHT * depth_part
        + ACTIVITY_SUB_WEIGHT * activity_part
    )
    return score, notes


def resolution_score(market):
    notes = []
    score = 100.0
    text = (market["description"] or "").lower()

    if not market["resolution_source"] and "http" not in text:
        score -= 25.0
        notes.append("no named resolution source")

    if len(text) < 200:
        score -= 15.0
        notes.append("thin resolution rules")

    hits = [phrase for phrase in AMBIGUITY_PHRASES if phrase in text]
    if hits:
        score -= min(30.0, 12.0 * len(hits))
        notes.append("subjective wording: " + ", ".join(hits[:3]))

    if "50-50" in text or "50/50" in text:
        score -= 5.0
        notes.append("has a 50-50 fallback clause")

    if "disput" in (market["uma_status"] or "").lower():
        score -= 40.0
        notes.append("UMA resolution disputed")

    return max(0.0, min(100.0, score)), notes


def time_score(market):
    days = market["days_left"]
    for limit, value in TIME_BANDS:
        if days <= limit:
            return value, []
    return 5.0, ["capital locked over a year"]


def favorite_flag(market):
    price = market["favorite_price"]
    if price is None or price < FAVORITE_PRICE_MIN or price >= 1.0:
        return None

    gain_pct = (1.0 - price) / price * 100.0
    loss_ratio = price / (1.0 - price)

    return {
        "outcome": market["favorite_outcome"],
        "price": price,
        "gain_pct": gain_pct,
        "loss_ratio": loss_ratio,
        "warning": f"one loss wipes out {loss_ratio:.0f} wins",
    }


def screen_market(market):
    execution, execution_notes = execution_score(market)
    resolution, resolution_notes = resolution_score(market)
    timing, time_notes = time_score(market)

    safety = (
        EXECUTION_WEIGHT * execution
        + RESOLUTION_WEIGHT * resolution
        + TIME_WEIGHT * timing
    )

    return {
        **market,
        "execution_score": round(execution, 1),
        "resolution_score": round(resolution, 1),
        "time_score": round(timing, 1),
        "safety_score": round(safety, 1),
        "favorite": favorite_flag(market),
        "notes": execution_notes + resolution_notes + time_notes,
    }
