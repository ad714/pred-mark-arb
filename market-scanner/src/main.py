import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.match.fliq_classifier import is_match_event
from src.search.poly_search import search_polymarket
from src.match.poly_matcher import compute_match_score, classify_match

IN_FILE = "data/derived/fliq_match_search_queue.json"
OUT_FILE = "data/derived/fliq_vs_poly_scored.json"

AUTO_MATCHED_FILE = "data/derived/auto_matched.json"
NEEDS_REVIEW_FILE = "data/derived/needs_review.json"
NO_MATCH_FILE = "data/derived/no_match.json"
PENDING_FILE = "data/derived/pending_on_polymarket.json"

# Polymarket usually lists fixtures only ~7 days ahead
POLY_FIXTURE_HORIZON_DAYS = 7


def main():
    Path("data/derived").mkdir(parents=True, exist_ok=True)

    with open(IN_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    output = []

    now = datetime.now(timezone.utc)
    poly_horizon = now + timedelta(days=POLY_FIXTURE_HORIZON_DAYS)

    print(f"Scoring Polymarket matches for {len(queue)} Fliq events...\n")

    for item in queue:
        parent = item.get("parent_question", "")
        query = item.get("search_query", "")
        end_date_raw = item.get("end_date")

        # 🔒 HARD GATE: only real match events
        if not is_match_event(parent):
            continue

        print(f"→ {query}")

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

        # ---------- NEW: pending_on_polymarket ----------
        if status == "no_match" and end_date_raw:
            try:
                event_end = datetime.fromisoformat(end_date_raw)
                if event_end > poly_horizon:
                    status = "pending_on_polymarket"
            except ValueError:
                pass  # keep original status if date parsing fails

        output.append({
            "parent_question_id": item["parent_question_id"],
            "parent_question": parent,
            "search_query": query,
            "end_date": end_date_raw,
            "status": status,
            "best_match": best,
            "all_candidates": scored[:5]
        })

    # ---------- SAVE FULL OUTPUT ----------
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # ---------- SPLIT BY STATUS ----------
    auto_matched = []
    needs_review = []
    no_match = []
    pending = []

    for item in output:
        if item["status"] == "matched":
            auto_matched.append(item)
        elif item["status"] == "review":
            needs_review.append(item)
        elif item["status"] == "pending_on_polymarket":
            pending.append(item)
        else:
            no_match.append(item)

    with open(AUTO_MATCHED_FILE, "w", encoding="utf-8") as f:
        json.dump(auto_matched, f, indent=2)

    with open(NEEDS_REVIEW_FILE, "w", encoding="utf-8") as f:
        json.dump(needs_review, f, indent=2)

    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=2)

    with open(NO_MATCH_FILE, "w", encoding="utf-8") as f:
        json.dump(no_match, f, indent=2)

    print("\nSaved files:")
    print(f" - {OUT_FILE}")
    print(f" - {AUTO_MATCHED_FILE} ({len(auto_matched)})")
    print(f" - {NEEDS_REVIEW_FILE} ({len(needs_review)})")
    print(f" - {PENDING_FILE} ({len(pending)})")
    print(f" - {NO_MATCH_FILE} ({len(no_match)})")


if __name__ == "__main__":
    main()
