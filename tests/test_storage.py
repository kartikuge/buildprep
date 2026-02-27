from datetime import date, datetime

import pytest

from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    CheckInStatus,
    Subject,
)
from preptrack.models.plan import DailyPlan, PlanCard, WeeklyPlan
from preptrack.models.user import (
    ActivityLogEntry,
    DayActivity,
    RecoveryState,
    TopicConfidence,
    UserProfile,
)
from preptrack.storage.dynamo_local import DynamoLocalStorage


@pytest.fixture
def storage():
    """Requires DynamoDB Local running on localhost:8000."""
    try:
        s = DynamoLocalStorage()
        return s
    except Exception:
        pytest.skip("DynamoDB Local not available")


@pytest.mark.integration
class TestStorageRoundTrips:
    def test_user_profile(self, storage):
        profile = UserProfile(
            user_id="storage-test-1",
            display_name="Storage Test",
            stage="both",
            prelims_date=date(2026, 5, 25),
            available_hours_per_day=6.0,
        )
        storage.save_user_profile(profile)
        loaded = storage.get_user_profile("storage-test-1")
        assert loaded is not None
        assert loaded.user_id == "storage-test-1"
        assert loaded.display_name == "Storage Test"
        assert loaded.available_hours_per_day == 6.0

    def test_user_profile_not_found(self, storage):
        assert storage.get_user_profile("nonexistent") is None

    def test_topic_confidence(self, storage):
        tc = TopicConfidence(
            user_id="storage-test-2",
            subject=Subject.HISTORY,
            perceived_confidence=3.5,
            streak=5,
            total_sessions=15,
            milestones_awarded=["streak_5"],
        )
        storage.save_topic_confidence("storage-test-2", tc)
        loaded = storage.get_topic_confidences("storage-test-2")
        assert len(loaded) >= 1
        history = [x for x in loaded if x.subject == Subject.HISTORY][0]
        assert history.perceived_confidence == 3.5
        assert history.streak == 5
        assert "streak_5" in history.milestones_awarded

    def test_weekly_plan(self, storage):
        plan = WeeklyPlan(
            user_id="storage-test-3",
            week_start=date(2026, 3, 2),
            days=[
                DailyPlan(
                    date=date(2026, 3, 2),
                    cards=[
                        PlanCard(
                            card_id="card-1",
                            block_type=BlockType.DEEP_STUDY,
                            category=BlockCategory.CORE_LEARNING,
                            subject=Subject.HISTORY,
                            topic="Parliament",
                            planned_duration=90,
                            fatigue=3,
                            order=0,
                        )
                    ],
                )
            ],
            narrative="Test week",
        )
        storage.save_weekly_plan(plan)
        loaded = storage.get_weekly_plan("storage-test-3", date(2026, 3, 2))
        assert loaded is not None
        assert len(loaded.days) == 1
        assert loaded.days[0].cards[0].subject == Subject.HISTORY

    def test_activity_log(self, storage):
        activity = DayActivity(
            user_id="storage-test-4",
            date=date(2026, 3, 2),
            entries=[
                ActivityLogEntry(
                    card_id="card-1",
                    block_type=BlockType.DEEP_STUDY,
                    subject=Subject.HISTORY,
                    topic="Parliament",
                    planned_duration=90,
                    actual_duration=85,
                    status=CheckInStatus.DONE,
                )
            ],
            finalized=True,
            finalized_at=datetime(2026, 3, 2, 20, 0),
        )
        storage.save_activity_log(activity)
        loaded = storage.get_activity_log("storage-test-4", date(2026, 3, 2))
        assert loaded is not None
        assert loaded.finalized is True
        assert loaded.entries[0].status == CheckInStatus.DONE

    def test_pending_days(self, storage):
        for i in range(3):
            d = date(2026, 3, 2 + i)
            activity = DayActivity(
                user_id="storage-test-5",
                date=d,
                finalized=(i == 1),  # Only middle day finalized
            )
            storage.save_activity_log(activity)
        pending = storage.get_pending_days("storage-test-5", date(2026, 3, 2))
        assert len(pending) == 2  # First and third are pending

    def test_recovery_state(self, storage):
        state = RecoveryState(
            user_id="storage-test-6",
            missed_dates=[date(2026, 3, 1), date(2026, 3, 2)],
            recovery_window_days=3,
        )
        storage.save_recovery_state(state)
        loaded = storage.get_recovery_state("storage-test-6")
        assert loaded is not None
        assert len(loaded.missed_dates) == 2
        assert loaded.recovery_window_days == 3
