import json
from pathlib import Path

from src.search.poly_search import search_polymarket
from src.match.poly_matcher import compute_match_score, classify_match
from src.match.fliq_classifier import is_match_event

NO_MATCH_FILE = "data/derived/no_match.json"
AUTO_MATCHED_FILE = "data/derived/auto_matched.json"
NEEDS_REVIEW_FILE = "data/derived/needs_review.json"


def load_json(path, default):
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    print("Rechecking pending Fliq matches on Polymarket...\n")

    no_match = load_json(NO_MATCH_FILE, [])
    auto_matched = load_json(AUTO_MATCHED_FILE, [])
    needs_review = load_json(NEEDS_REVIEW_FILE, [])

    still_pending = []

    for item in no_match:
        parent = item.get("parent_question", "")
        query = item.get("search_query", "")

        if not is_match_event(parent):
            continue

        print(f"→ Rechecking: {query}")

        poly_results = search_polymarket(query)

        scored = []
        for poly in poly_results or []:
            score = compute_match_score(item, poly)
            scored.append({
                "poly_id": poly.get("id"),
                "poly_title": poly.get("title"),
                "poly_url": f"https://polymarket.com/event/{poly.get('slug')}",
                "score": round(score, 4)
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        best = scored[0] if scored else None
        status = classify_match(best["score"]) if best else "no_match"

        updated_item = {
            **item,
            "status": status,
            "best_match": best,
            "all_candidates": scored[:5]
        }

        if status == "matched":
            auto_matched.append(updated_item)
            print("   ✓ Promoted to AUTO MATCHED")

        elif status == "review":
            needs_review.append(updated_item)
            print("   ⚠ Moved to NEEDS REVIEW")

        else:
            still_pending.append(item)

    save_json(AUTO_MATCHED_FILE, auto_matched)
    save_json(NEEDS_REVIEW_FILE, needs_review)
    save_json(NO_MATCH_FILE, still_pending)

    print("\nRecheck complete.")
    print(f"Auto matched: {len(auto_matched)}")
    print(f"Needs review: {len(needs_review)}")
    print(f"Still pending: {len(still_pending)}")


if __name__ == "__main__":
    main()
