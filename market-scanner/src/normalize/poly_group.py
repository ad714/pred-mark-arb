def normalize_poly_event(event: dict):
    title = event.get("title", "")
    if " vs. " not in title:
        return None

    home, away = title.split(" vs. ", 1)
    home = home.replace(" CF", "").strip()
    away = away.replace(" FC", "").strip()

    start_time = event.get("startTime")

    outcomes = {}

    for m in event.get("markets", []):
        q = m.get("question", "").lower()
        prices = m.get("outcomePrices", [])
        if not prices:
            continue

        yes_price = float(prices[0])

        if "win" in q and home.lower() in q:
            outcomes["home"] = {
                "price": yes_price,
                "market_id": m["id"]
            }
        elif "win" in q and away.lower() in q:
            outcomes["away"] = {
                "price": yes_price,
                "market_id": m["id"]
            }
        elif "draw" in q:
            outcomes["draw"] = {
                "price": yes_price,
                "market_id": m["id"]
            }

    if len(outcomes) < 2:
        return None

    return {
    "platform": "polymarket",
    "event_id": event["id"],
    "slug": "la-liga-2025/games/week/12/lal-vil-bar-2025-12-21",
    "sport": "football",
    "competition": "La Liga",
    "event": {
        "home": home,
        "away": away,
        "participants": [home, away],
        "start_time_utc": start_time
    },
    "market_type": "match_winner",
    "outcomes": outcomes
}
