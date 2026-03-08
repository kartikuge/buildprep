from datetime import date, datetime

import pytest

from preptrack.engine.confidence import process_checkin
from preptrack.kb.confidence import CONFIDENCE_CONFIG
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
                            fatigue=2,
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


@pytest.mark.integration
class TestCheckInStorageIntegration:
    """DynamoDB round-trip tests for the check-in + confidence flow."""

    def _make_plan_with_cards(self, user_id, week_start):
        cards = [
            PlanCard(
                card_id=f"{user_id}-history",
                block_type=BlockType.DEEP_STUDY,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.HISTORY,
                topic="Ancient India",
                planned_duration=90,
                fatigue=2,
                order=0,
            ),
            PlanCard(
                card_id=f"{user_id}-polity",
                block_type=BlockType.DEEP_STUDY,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.POLITY,
                topic="Parliament",
                planned_duration=60,
                fatigue=2,
                order=1,
            ),
            PlanCard(
                card_id=f"{user_id}-news",
                block_type=BlockType.NEWS_READING,
                category=BlockCategory.INPUT,
                subject=None,
                topic=None,
                planned_duration=30,
                fatigue=0,
                order=2,
            ),
        ]
        day = DailyPlan(date=week_start, cards=cards)
        return WeeklyPlan(
            user_id=user_id,
            week_start=week_start,
            days=[day],
            narrative="Check-in integration test.",
        )

    def test_card_status_persists_after_save(self, storage):
        """Updating card status on a plan and saving persists through reload."""
        uid = "checkin-store-1"
        ws = date(2026, 3, 9)
        plan = self._make_plan_with_cards(uid, ws)
        storage.save_weekly_plan(plan)

        # Simulate check-in: update card status
        loaded = storage.get_weekly_plan(uid, ws)
        card = next(c for c in loaded.days[0].cards if c.card_id == f"{uid}-history")
        card.status = CheckInStatus.DONE
        card.actual_duration = 90
        storage.save_weekly_plan(loaded)

        # Reload and verify
        reloaded = storage.get_weekly_plan(uid, ws)
        card = next(c for c in reloaded.days[0].cards if c.card_id == f"{uid}-history")
        assert card.status == CheckInStatus.DONE
        assert card.actual_duration == 90

    def test_finalize_day_persists(self, storage):
        """Setting finalized=True + finalized_at persists through reload."""
        uid = "checkin-store-2"
        ws = date(2026, 3, 9)
        plan = self._make_plan_with_cards(uid, ws)
        storage.save_weekly_plan(plan)

        loaded = storage.get_weekly_plan(uid, ws)
        day = loaded.days[0]
        for card in day.cards:
            if card.status == CheckInStatus.PENDING:
                card.status = CheckInStatus.SKIPPED
        day.finalized = True
        day.finalized_at = datetime(2026, 3, 9, 20, 30)
        storage.save_weekly_plan(loaded)

        reloaded = storage.get_weekly_plan(uid, ws)
        assert reloaded.days[0].finalized is True
        assert reloaded.days[0].finalized_at is not None
        statuses = [c.status for c in reloaded.days[0].cards]
        assert CheckInStatus.PENDING not in statuses

    def test_confidence_upsert_roundtrip(self, storage):
        """save_topic_confidence should upsert: update existing, not duplicate."""
        uid = "checkin-store-3"

        # Save initial
        tc = TopicConfidence(
            user_id=uid,
            subject=Subject.HISTORY,
            perceived_confidence=2.5,
            streak=0,
            total_sessions=0,
        )
        storage.save_topic_confidence(uid, tc)

        # Simulate check-in: process and save updated
        updated = process_checkin(tc, CheckInStatus.DONE, CONFIDENCE_CONFIG, date(2026, 3, 9))
        storage.save_topic_confidence(uid, updated)

        # Reload — should be exactly 1 HISTORY entry
        confs = storage.get_topic_confidences(uid)
        history_confs = [c for c in confs if c.subject == Subject.HISTORY]
        assert len(history_confs) == 1
        assert history_confs[0].streak == 1
        assert history_confs[0].total_sessions == 1

    def test_confidence_multiple_subjects_independent(self, storage):
        """Different subjects are stored independently."""
        uid = "checkin-store-4"

        for subj in [Subject.HISTORY, Subject.POLITY, Subject.ECONOMY]:
            tc = TopicConfidence(
                user_id=uid,
                subject=subj,
                perceived_confidence=2.0,
            )
            storage.save_topic_confidence(uid, tc)

        # Update only HISTORY
        confs = storage.get_topic_confidences(uid)
        history = next(c for c in confs if c.subject == Subject.HISTORY)
        updated = process_checkin(history, CheckInStatus.DONE, CONFIDENCE_CONFIG, date(2026, 3, 9))
        storage.save_topic_confidence(uid, updated)

        # Verify HISTORY updated, others unchanged
        confs = storage.get_topic_confidences(uid)
        assert len(confs) == 3
        h = next(c for c in confs if c.subject == Subject.HISTORY)
        p = next(c for c in confs if c.subject == Subject.POLITY)
        assert h.streak == 1
        assert p.streak == 0

    def test_activity_log_with_checkin_entries(self, storage):
        """Activity log stores check-in entries with correct statuses."""
        uid = "checkin-store-5"

        activity = DayActivity(
            user_id=uid,
            date=date(2026, 3, 9),
            entries=[
                ActivityLogEntry(
                    card_id="c1",
                    block_type=BlockType.DEEP_STUDY,
                    subject=Subject.HISTORY,
                    topic="Ancient India",
                    planned_duration=90,
                    actual_duration=90,
                    status=CheckInStatus.DONE,
                ),
                ActivityLogEntry(
                    card_id="c2",
                    block_type=BlockType.DEEP_STUDY,
                    subject=Subject.POLITY,
                    topic="Parliament",
                    planned_duration=60,
                    actual_duration=40,
                    status=CheckInStatus.PARTIAL,
                ),
                ActivityLogEntry(
                    card_id="c3",
                    block_type=BlockType.NEWS_READING,
                    subject=None,
                    topic=None,
                    planned_duration=30,
                    actual_duration=None,
                    status=CheckInStatus.SKIPPED,
                ),
            ],
            finalized=True,
            finalized_at=datetime(2026, 3, 9, 21, 0),
        )
        storage.save_activity_log(activity)

        loaded = storage.get_activity_log(uid, date(2026, 3, 9))
        assert loaded is not None
        assert len(loaded.entries) == 3
        assert loaded.finalized is True

        done_entry = next(e for e in loaded.entries if e.card_id == "c1")
        assert done_entry.status == CheckInStatus.DONE
        assert done_entry.actual_duration == 90

        partial_entry = next(e for e in loaded.entries if e.card_id == "c2")
        assert partial_entry.status == CheckInStatus.PARTIAL
        assert partial_entry.actual_duration == 40

        skipped_entry = next(e for e in loaded.entries if e.card_id == "c3")
        assert skipped_entry.status == CheckInStatus.SKIPPED
        assert skipped_entry.subject is None
