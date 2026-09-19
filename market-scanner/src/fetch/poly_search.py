import requests

POLY_SEARCH_API = "https://gamma-api.polymarket.com/public-search"

def search_poly_event(home: str, away: str):
    query = f"{home} vs {away}"

    params = {
        "q": query
    }

    r = requests.get(POLY_SEARCH_API, params=params, timeout=10)
    if r.status_code != 200:
        return None

    results = r.json()
    if not results:
        return None

    # Return best candidate for now
    return results[0]
