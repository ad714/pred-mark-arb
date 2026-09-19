from src.utils.event_links import polymarket_event_link, fliq_event_link

def build_market_view(poly: dict, fliq: dict):
    return {
        "event": f"{poly['event']['home']} vs {poly['event']['away']}",
        "competition": poly["competition"],
        "market_type": poly["market_type"],
        "links": {
            "polymarket": polymarket_event_link(poly),
            "fliq": fliq_event_link(
                fliq["event_id"],
                fliq["outcomes"]["home"]["market_id"]
            )
        }
    }
