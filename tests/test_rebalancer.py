"""Unit tests for rebalancer: day classification, missed content extraction, fatigue carryover."""

from datetime import date

import pytest

from preptrack.agent.rebalancer import (
    classify_days,
    compute_fatigue_carryover,
    count_frozen_ca_integrations,
    extract_missed_content,
)
from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    CheckInStatus,
    Subject,
)
from preptrack.models.plan import DailyPlan, PlanCard, WeeklyPlan

from tests.conftest import make_card, make_daily, make_weekly


def _card(
    status: CheckInStatus = CheckInStatus.PENDING,
    block_type: BlockType = BlockType.REVISION,
    fatigue: int = 1,
    subject: Subject | None = Subject.HISTORY,
    duration: int = 45,
    order: int = 0,
) -> PlanCard:
    return PlanCard(
        block_type=block_type,
        category=BlockCategory.CORE_RETENTION,
        subject=subject,
        topic="Test Topic",
        planned_duration=duration,
        fatigue=fatigue,
        order=order,
        status=status,
    )


# ── Day Classification ──────────────────────────────────────────────


class TestClassifyDays:
    """Tests for classify_days()."""

    def test_all_pending_past_days_are_missed(self):
        """Past days with all PENDING cards → missed."""
        today = date(2026, 3, 11)  # Wednesday
        mon = make_daily(date(2026, 3, 9), [_card()])
        tue = make_daily(date(2026, 3, 10), [_card()])
        wed = make_daily(today, [_card()])
        plan = make_weekly("u1", date(2026, 3, 9), [mon, tue, wed])

        frozen, missed, eligible = classify_days(plan, today)
        assert len(frozen) == 0
        assert len(missed) == 2  # Mon, Tue
        assert len(eligible) == 1  # Wed (today)

    def test_done_cards_freeze_day(self):
        """Day with at least 1 DONE card → frozen."""
        today = date(2026, 3, 11)
        mon = make_daily(date(2026, 3, 9), [
            _card(status=CheckInStatus.DONE),
            _card(status=CheckInStatus.SKIPPED, order=1),
        ])
        tue = make_daily(date(2026, 3, 10), [_card()])
        plan = make_weekly("u1", date(2026, 3, 9), [mon, tue])

        frozen, missed, eligible = classify_days(plan, today)
        assert len(frozen) == 1
        assert frozen[0].date == date(2026, 3, 9)
        assert len(missed) == 1  # Tue is past + all pending

    def test_partial_cards_freeze_day(self):
        """Day with PARTIAL card → frozen (not rebalanced)."""
        today = date(2026, 3, 11)
        mon = make_daily(date(2026, 3, 9), [
            _card(status=CheckInStatus.PARTIAL),
        ])
        plan = make_weekly("u1", date(2026, 3, 9), [mon])

        frozen, missed, eligible = classify_days(plan, today)
        assert len(frozen) == 1
        assert len(missed) == 0

    def test_all_skipped_past_day_is_missed(self):
        """Past day where all cards are SKIPPED → missed."""
        today = date(2026, 3, 11)
        mon = make_daily(date(2026, 3, 9), [
            _card(status=CheckInStatus.SKIPPED),
            _card(status=CheckInStatus.SKIPPED, order=1),
        ])
        plan = make_weekly("u1", date(2026, 3, 9), [mon])

        frozen, missed, eligible = classify_days(plan, today)
        assert len(missed) == 1
        assert len(frozen) == 0

    def test_today_and_future_are_eligible(self):
        """Today and future unfrozen days → eligible for recovery."""
        today = date(2026, 3, 11)  # Wed
        wed = make_daily(date(2026, 3, 11), [_card()])
        thu = make_daily(date(2026, 3, 12), [_card()])
        fri = make_daily(date(2026, 3, 13), [_card()])
        plan = make_weekly("u1", date(2026, 3, 9), [wed, thu, fri])

        frozen, missed, eligible = classify_days(plan, today)
        assert len(eligible) == 3
        assert eligible[0].date == today

    def test_mixed_week(self):
        """Full week: some frozen, some missed, some eligible."""
        today = date(2026, 3, 12)  # Thu
        week_start = date(2026, 3, 9)  # Mon
        days = []
        # Mon: DONE → frozen
        days.append(make_daily(date(2026, 3, 9), [_card(status=CheckInStatus.DONE)]))
        # Tue: all PENDING, past → missed
        days.append(make_daily(date(2026, 3, 10), [_card()]))
        # Wed: all SKIPPED, past → missed
        days.append(make_daily(date(2026, 3, 11), [_card(status=CheckInStatus.SKIPPED)]))
        # Thu (today): PENDING → eligible
        days.append(make_daily(date(2026, 3, 12), [_card()]))
        # Fri-Sun: PENDING → eligible
        for i in range(13, 16):
            days.append(make_daily(date(2026, 3, i), [_card()]))

        plan = make_weekly("u1", week_start, days)
        frozen, missed, eligible = classify_days(plan, today)

        assert len(frozen) == 1  # Mon
        assert len(missed) == 2  # Tue, Wed
        assert len(eligible) == 4  # Thu, Fri, Sat, Sun


# ── Missed Content Extraction ───────────────────────────────────────


class TestExtractMissedContent:
    def test_extracts_all_cards_from_missed_days(self):
        missed = [
            make_daily(date(2026, 3, 10), [
                _card(subject=Subject.POLITY, block_type=BlockType.DEEP_STUDY, duration=90),
                _card(subject=Subject.ECONOMY, block_type=BlockType.REVISION, duration=60, order=1),
            ]),
            make_daily(date(2026, 3, 11), [
                _card(subject=None, block_type=BlockType.NEWS_READING, duration=20),
            ]),
        ]
        content = extract_missed_content(missed)
        assert len(content) == 3
        assert content[0]["subject"] == "POLITY"
        assert content[0]["block_type"] == "DEEP_STUDY"
        assert content[0]["planned_duration"] == 90
        assert content[2]["subject"] is None

    def test_empty_missed_returns_empty(self):
        assert extract_missed_content([]) == []


# ── Fatigue Carryover ───────────────────────────────────────────────


class TestFatigueCarryover:
    def test_no_frozen_days_returns_zero(self):
        assert compute_fatigue_carryover([], date(2026, 3, 12)) == 0

    def test_consecutive_heavy_days(self):
        """3 consecutive heavy days before recovery → carryover = 3."""
        frozen = [
            make_daily(date(2026, 3, 9), [_card(fatigue=3)]),   # Mon heavy
            make_daily(date(2026, 3, 10), [_card(fatigue=3)]),  # Tue heavy
            make_daily(date(2026, 3, 11), [_card(fatigue=3)]),  # Wed heavy
        ]
        assert compute_fatigue_carryover(frozen, date(2026, 3, 12)) == 3

    def test_light_day_breaks_streak(self):
        """Light day in between resets the count."""
        frozen = [
            make_daily(date(2026, 3, 9), [_card(fatigue=3)]),   # Mon heavy
            make_daily(date(2026, 3, 10), [_card(fatigue=1)]),  # Tue light
            make_daily(date(2026, 3, 11), [_card(fatigue=3)]),  # Wed heavy
        ]
        assert compute_fatigue_carryover(frozen, date(2026, 3, 12)) == 1

    def test_all_light_days(self):
        frozen = [
            make_daily(date(2026, 3, 9), [_card(fatigue=1)]),
            make_daily(date(2026, 3, 10), [_card(fatigue=2)]),
        ]
        assert compute_fatigue_carryover(frozen, date(2026, 3, 12)) == 0

    def test_ignores_days_after_recovery_start(self):
        """Only consider frozen days BEFORE recovery_start."""
        frozen = [
            make_daily(date(2026, 3, 9), [_card(fatigue=3)]),
            make_daily(date(2026, 3, 13), [_card(fatigue=3)]),  # After recovery
        ]
        assert compute_fatigue_carryover(frozen, date(2026, 3, 12)) == 1


# ── CA Integration Count ────────────────────────────────────────────


class TestCountFrozenCA:
    def test_counts_ca_blocks(self):
        frozen = [
            make_daily(date(2026, 3, 9), [
                _card(block_type=BlockType.CA_INTEGRATION),
                _card(block_type=BlockType.REVISION, order=1),
            ]),
        ]
        assert count_frozen_ca_integrations(frozen) == 1

    def test_no_ca_returns_zero(self):
        frozen = [
            make_daily(date(2026, 3, 9), [_card(block_type=BlockType.REVISION)]),
        ]
        assert count_frozen_ca_integrations(frozen) == 0

    def test_empty_frozen(self):
        assert count_frozen_ca_integrations([]) == 0
