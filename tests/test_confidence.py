from datetime import date

import pytest

from preptrack.engine.confidence import (
    apply_completion,
    apply_inactivity_decay,
    apply_skip,
    process_checkin,
)
from preptrack.models.enums import CheckInStatus, Subject
from preptrack.models.user import TopicConfidence


@pytest.fixture
def base_topic():
    return TopicConfidence(
        user_id="test",
        subject=Subject.POLITY,
        perceived_confidence=2.5,
        streak=0,
        skip_count=0,
        total_sessions=0,
    )


class TestApplyCompletion:
    def test_increments_streak_and_sessions(self, base_topic, confidence_config):
        result = apply_completion(base_topic, confidence_config, date(2026, 3, 1))
        assert result.streak == 1
        assert result.total_sessions == 1
        assert result.skip_count == 0
        assert result.last_practiced_date == date(2026, 3, 1)

    def test_resets_skip_count(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=2.5, skip_count=5,
        )
        result = apply_completion(topic, confidence_config, date(2026, 3, 1))
        assert result.skip_count == 0

    def test_streak_milestone_5(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=2.0, streak=4, total_sessions=4,
        )
        result = apply_completion(topic, confidence_config, date(2026, 3, 1))
        assert result.streak == 5
        assert "streak_5" in result.milestones_awarded
        assert result.perceived_confidence == 2.3  # 2.0 + 0.3

    def test_streak_milestone_one_shot(self, confidence_config):
        """Streak milestone cannot fire twice."""
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=2.3, streak=4, total_sessions=5,
            milestones_awarded=["streak_5"],
        )
        result = apply_completion(topic, confidence_config, date(2026, 3, 1))
        assert result.perceived_confidence == 2.3  # No additional bonus

    def test_session_milestone_10(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=2.0, streak=0, total_sessions=9,
        )
        result = apply_completion(topic, confidence_config, date(2026, 3, 1))
        assert result.total_sessions == 10
        assert "total_10" in result.milestones_awarded
        assert result.perceived_confidence == 2.2

    def test_session_recurring_at_25(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=3.0, streak=0, total_sessions=24,
            milestones_awarded=["total_10", "total_20"],
        )
        result = apply_completion(topic, confidence_config, date(2026, 3, 1))
        assert result.total_sessions == 25
        assert "total_25" in result.milestones_awarded
        assert result.perceived_confidence == 3.2

    def test_session_recurring_at_30(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=3.0, streak=0, total_sessions=29,
            milestones_awarded=["total_10", "total_20", "total_25"],
        )
        result = apply_completion(topic, confidence_config, date(2026, 3, 1))
        assert result.total_sessions == 30
        assert "total_30" in result.milestones_awarded
        assert result.perceived_confidence == 3.2

    def test_clamp_at_5(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=4.9, streak=4, total_sessions=9,
        )
        result = apply_completion(topic, confidence_config, date(2026, 3, 1))
        # streak_5 (+0.3) + total_10 (+0.2) = 4.9 + 0.5 = 5.4 → clamped to 5.0
        assert result.perceived_confidence == 5.0


class TestApplySkip:
    def test_increments_skip_and_resets_streak(self, base_topic, confidence_config):
        topic = base_topic.model_copy(update={"streak": 5})
        result = apply_skip(topic, confidence_config)
        assert result.skip_count == 1
        assert result.streak == 0

    def test_penalty_at_3(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=3.0, skip_count=2,
        )
        result = apply_skip(topic, confidence_config)
        assert result.skip_count == 3
        assert result.perceived_confidence == 2.8  # 3.0 - 0.2

    def test_penalty_at_7(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=3.0, skip_count=6,
        )
        result = apply_skip(topic, confidence_config)
        assert result.skip_count == 7
        assert result.perceived_confidence == 2.7  # 3.0 - 0.3

    def test_penalty_at_11(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=3.0, skip_count=10,
        )
        result = apply_skip(topic, confidence_config)
        assert result.skip_count == 11
        assert result.perceived_confidence == 2.6  # 3.0 - 0.4

    def test_no_penalty_past_11(self, confidence_config):
        """No further penalties beyond skip 11."""
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=2.6, skip_count=11,
        )
        result = apply_skip(topic, confidence_config)
        assert result.skip_count == 12
        assert result.perceived_confidence == 2.6

    def test_clamp_at_1(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=1.1, skip_count=2,
        )
        result = apply_skip(topic, confidence_config)
        assert result.perceived_confidence == 1.0  # 1.1 - 0.2 = 0.9 → clamped to 1.0


class TestInactivityDecay:
    def test_no_decay_under_7_days(self, base_topic, confidence_config):
        topic = base_topic.model_copy(update={"last_practiced_date": date(2026, 2, 20)})
        result = apply_inactivity_decay(topic, confidence_config, date(2026, 2, 25))
        assert result.perceived_confidence == topic.perceived_confidence

    def test_decay_at_7_days(self, base_topic, confidence_config):
        topic = base_topic.model_copy(update={"last_practiced_date": date(2026, 2, 18)})
        result = apply_inactivity_decay(topic, confidence_config, date(2026, 2, 25))
        assert result.perceived_confidence == 2.4  # 2.5 - 0.1

    def test_decay_at_14_days_resets_streak(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=3.0, streak=5,
            last_practiced_date=date(2026, 2, 10),
        )
        result = apply_inactivity_decay(topic, confidence_config, date(2026, 2, 25))
        # 15 days → 2 periods → -0.2
        assert abs(result.perceived_confidence - 2.8) < 1e-9
        assert result.streak == 0

    def test_maintenance_decay_halved(self, confidence_config):
        topic = TopicConfidence(
            user_id="test", subject=Subject.POLITY,
            perceived_confidence=4.0, streak=12, total_sessions=55,
            last_practiced_date=date(2026, 2, 11),
        )
        result = apply_inactivity_decay(topic, confidence_config, date(2026, 2, 25))
        # 14 days → 2 periods → -0.05 * 2 = -0.10
        assert abs(result.perceived_confidence - 3.9) < 1e-9

    def test_no_last_practiced_noop(self, base_topic, confidence_config):
        result = apply_inactivity_decay(base_topic, confidence_config, date(2026, 2, 25))
        assert result.perceived_confidence == base_topic.perceived_confidence


class TestProcessCheckin:
    def test_done_fires_completion(self, base_topic, confidence_config):
        result = process_checkin(base_topic, CheckInStatus.DONE, confidence_config, date(2026, 3, 1))
        assert result.streak == 1
        assert result.total_sessions == 1

    def test_partial_fires_completion(self, base_topic, confidence_config):
        result = process_checkin(base_topic, CheckInStatus.PARTIAL, confidence_config, date(2026, 3, 1))
        assert result.streak == 1

    def test_skipped_fires_skip(self, base_topic, confidence_config):
        result = process_checkin(base_topic, CheckInStatus.SKIPPED, confidence_config, date(2026, 3, 1))
        assert result.skip_count == 1

    def test_inactive_is_noop(self, base_topic, confidence_config):
        result = process_checkin(base_topic, CheckInStatus.INACTIVE, confidence_config, date(2026, 3, 1))
        assert result == base_topic

    def test_pending_is_noop(self, base_topic, confidence_config):
        result = process_checkin(base_topic, CheckInStatus.PENDING, confidence_config, date(2026, 3, 1))
        assert result == base_topic
