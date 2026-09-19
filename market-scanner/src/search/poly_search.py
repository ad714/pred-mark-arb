import requests

SEARCH_API = "https://gamma-api.polymarket.com/public-search"

def search_polymarket(query: str, limit: int = 10):
    params = {
        "q": query,
        "limit": limit,
    }

    r = requests.get(SEARCH_API, params=params, timeout=15)
    r.raise_for_status()

    data = r.json()

    events = []

    for ev in data.get("events", []):
        events.append({
            "id": ev.get("id"),
            "title": ev.get("title"),
            "slug": ev.get("slug"),
            "startDate": ev.get("startDate"),
            "tags": ev.get("tags", []),
        })

    return events
