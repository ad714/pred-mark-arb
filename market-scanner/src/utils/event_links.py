def polymarket_event_link(slug: str):
    """
    slug example:
    la-liga-2025/games/week/12/lal-vil-bar-2025-12-21
    """
    return f"https://polymarket.com/sports/{slug}"


def fliq_event_link(parent_question_id: str, op_id: str):
    """
    parent_question_id: 111340
    op_id: 17186 (any option, used to open page correctly)
    """
    return (
        "https://www.fliq.one/#/multi-question/"
        f"match-result-{parent_question_id}"
        f"?op={op_id}&referral=aD6VfTQkAW"
    )
