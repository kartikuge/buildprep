from datetime import date

from preptrack.models.enums import CheckInStatus
from preptrack.models.kb import ConfidenceConfig
from preptrack.models.user import TopicConfidence


def _clamp(value: float, config: ConfidenceConfig) -> float:
    return max(config.min_confidence, min(config.max_confidence, value))


def apply_completion(
    topic: TopicConfidence, config: ConfidenceConfig, practiced_date: date
) -> TopicConfidence:
    """Apply DONE or PARTIAL completion: streak++, skip_count=0, session++, milestones."""
    conf = topic.perceived_confidence
    streak = topic.streak + 1
    total_sessions = topic.total_sessions + 1
    awarded = list(topic.milestones_awarded)

    # Streak milestones (one-shot ever)
    for m in config.streak_milestones:
        key = f"streak_{m.streak}"
        if streak >= m.streak and key not in awarded:
            conf += m.bonus
            awarded.append(key)

    # Session milestones
    for m in config.session_milestones:
        key = f"total_{m.total_sessions}"
        if m.one_shot:
            if total_sessions >= m.total_sessions and key not in awarded:
                conf += m.bonus
                awarded.append(key)
        else:
            # Recurring every 5 sessions from this threshold onward
            if total_sessions >= m.total_sessions:
                # Check if we just crossed a recurring boundary
                if total_sessions % 5 == 0 and total_sessions >= m.total_sessions:
                    recurring_key = f"total_{total_sessions}"
                    if recurring_key not in awarded:
                        conf += m.bonus
                        awarded.append(recurring_key)

    return topic.model_copy(
        update={
            "perceived_confidence": _clamp(conf, config),
            "streak": streak,
            "skip_count": 0,
            "total_sessions": total_sessions,
            "last_practiced_date": practiced_date,
            "milestones_awarded": awarded,
        }
    )


def apply_skip(topic: TopicConfidence, config: ConfidenceConfig) -> TopicConfidence:
    """Apply SKIPPED: skip_count++, streak=0, penalties at exact threshold crossing."""
    conf = topic.perceived_confidence
    new_skip_count = topic.skip_count + 1

    # Skip penalties fire on exact crossing (old < threshold, new >= threshold)
    for p in config.skip_penalties:
        if topic.skip_count < p.skip_count and new_skip_count >= p.skip_count:
            conf -= p.penalty

    return topic.model_copy(
        update={
            "perceived_confidence": _clamp(conf, config),
            "skip_count": new_skip_count,
            "streak": 0,
        }
    )


def apply_inactivity_decay(
    topic: TopicConfidence, config: ConfidenceConfig, today: date
) -> TopicConfidence:
    """Apply inactivity decay: -0.1 per 7d (or -0.05 maintenance). Reset streak at 14d."""
    if topic.last_practiced_date is None:
        return topic

    days_inactive = (today - topic.last_practiced_date).days
    if days_inactive < 7:
        return topic

    # Determine decay rate
    is_maintenance = (
        topic.total_sessions >= config.maintenance_min_sessions
        and topic.streak >= config.maintenance_min_streak
    )
    decay_rate = config.maintenance_decay_per_7_days if is_maintenance else config.decay_per_7_days

    periods = days_inactive // 7
    total_decay = periods * decay_rate
    new_conf = _clamp(topic.perceived_confidence - total_decay, config)

    # Reset streak at 14 days
    new_streak = 0 if days_inactive >= config.streak_reset_days else topic.streak

    return topic.model_copy(
        update={
            "perceived_confidence": new_conf,
            "streak": new_streak,
        }
    )


def process_checkin(
    topic: TopicConfidence,
    status: CheckInStatus,
    config: ConfidenceConfig,
    today: date,
) -> TopicConfidence:
    """Dispatch check-in to appropriate handler. PARTIAL = completion. INACTIVE = no-op."""
    if status in (CheckInStatus.DONE, CheckInStatus.PARTIAL):
        return apply_completion(topic, config, today)
    if status == CheckInStatus.SKIPPED:
        return apply_skip(topic, config)
    # INACTIVE or PENDING — no-op
    return topic
