from datetime import date

from preptrack.models.kb import SubjectWeight
from preptrack.models.plan import SubjectPriority
from preptrack.models.user import TopicConfidence


def compute_recency_penalty(days_since_last: int | None) -> float:
    """Recency penalty: 1 + min(days/7, 3.0). None → 21 days (max penalty)."""
    if days_since_last is None:
        days_since_last = 21
    return 1.0 + min(days_since_last / 7.0, 3.0)


def compute_prelims_priority(
    confidence: float, weight: float, days_since_last: int | None
) -> float:
    """priority = (1 - conf/5) * weight * recency, floored at 0.01 * weight."""
    normalized = confidence / 5.0
    recency = compute_recency_penalty(days_since_last)
    raw = (1.0 - normalized) * weight * recency
    return max(raw, 0.01 * weight)


def rank_subjects(
    confidences: list[TopicConfidence],
    weights: list[SubjectWeight],
    today: date,
) -> list[SubjectPriority]:
    """Rank subjects by prelims priority, descending."""
    weight_map = {w.subject: w.prelims_weight for w in weights if w.prelims_weight is not None}
    results: list[SubjectPriority] = []

    for tc in confidences:
        w = weight_map.get(tc.subject)
        if w is None:
            continue
        if tc.last_practiced_date is not None:
            days_since = (today - tc.last_practiced_date).days
        else:
            days_since = None
        recency = compute_recency_penalty(days_since)
        raw = compute_prelims_priority(tc.perceived_confidence, w, days_since)
        results.append(
            SubjectPriority(
                subject=tc.subject,
                raw_priority=raw,
                normalized_confidence=tc.perceived_confidence / 5.0,
                weight=w,
                recency_penalty=recency,
            )
        )

    results.sort(key=lambda sp: sp.raw_priority, reverse=True)
    return results
