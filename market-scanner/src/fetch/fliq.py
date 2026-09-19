import requests

FLIQ_API = "https://auto-question.fliq.one/question"

def fetch_all_fliq_questions():
    all_questions = []
    page = 1
    limit = 100

    while True:
        params = {
            "page": page,
            "limit": limit,
            "status": "OPEN"
        }

        r = requests.get(FLIQ_API, params=params, timeout=15)
        r.raise_for_status()

        data = r.json()
        questions = data.get("questions", [])

        if not questions:
            break

        for q in questions:
            category = q.get("blockchainMetadata", {}).get("category", "").lower()
            if category in ("football", "cricket", "sports"):
                all_questions.append(q)

        page += 1

    print(f"Fetched Fliq questions (sports only): {len(all_questions)}")
    return all_questions
