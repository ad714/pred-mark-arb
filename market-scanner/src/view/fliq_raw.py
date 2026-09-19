from datetime import datetime, timezone


def build_fliq_raw_record(q: dict) -> dict:
    meta = q.get("blockchainMetadata", {})

    # Core fields
    question_id = q.get("questionId")
    question = meta.get("questionHeader", "").strip()
    category = q.get("category")
    is_settled = q.get("isSettled", False)
    created_at = q.get("createdAt")
    end_time = meta.get("questionEndTime")

    # Parent linkage (CRITICAL)
    parent_question_id = meta.get("parentQuestionId")
    parent_question = meta.get("parentQuestionHeader")

    # If parent header missing, this question itself is the root
    if not parent_question:
        parent_question = question
        parent_question_id = question_id

    # Convert end_time (unix) → ISO datetime (UTC)
    end_date = None
    if end_time:
        end_date = datetime.fromtimestamp(
            end_time, tz=timezone.utc
        ).isoformat()

    # Market link
    link = f"https://www.fliq.one/#/question/{question_id}"

    return {
        "question_id": question_id,
        "question": question,  # child title (e.g. BTTS)
        "parent_question_id": parent_question_id,
        "parent_question": parent_question,  # match-level title
        "category": category,
        "is_settled": is_settled,
        "created_at": created_at,
        "end_time": end_time,
        "end_date": end_date,
        "link": link,
    }
