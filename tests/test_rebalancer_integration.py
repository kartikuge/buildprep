"""Integration tests for rebalancing — requires AWS creds + Nova 2 Lite access.

Run with: pytest tests/test_rebalancer_integration.py -v -m integration -s
Detailed logs: pytest tests/test_rebalancer_integration.py -v -m integration -s --log-cli-level=INFO
"""

from datetime import date

import pytest

from preptrack.agent.planner import generate_plan
from preptrack.agent.rebalancer import (
    classify_days,
    compute_fatigue_carryover,
    count_frozen_ca_integrations,
    extract_missed_content,
    rebalance_plan,
)
from preptrack.engine.fatigue import compute_daily_fatigue_cap
from preptrack.engine.phase import determine_phase
from preptrack.engine.validator import validate_weekly_plan
from preptrack.kb import BLOCK_DEFINITIONS
from preptrack.models.enums import BlockType, CheckInStatus, Subject
from preptrack.models.plan import WeeklyPlan
from preptrack.models.user import TopicConfidence, UserProfile


def _has_aws_creds() -> bool:
    try:
        import boto3
        sts = boto3.client("sts")
        sts.get_caller_identity()
        return True
    except Exception:
        return False


skip_no_creds = pytest.mark.skipif(
    not _has_aws_creds(),
    reason="AWS credentials not available",
)

_BLOCK_LIMITS = {
    bd.block_type: (bd.min_duration, bd.max_duration) for bd in BLOCK_DEFINITIONS
}

_WEEK_START = date(2026, 3, 9)  # Monday
_TODAY = date(2026, 3, 12)  # Thursday — Mon done, Tue-Wed missed, Thu-Sun recovery


@pytest.fixture(scope="module")
def rebal_profile() -> UserProfile:
    return UserProfile(
        user_id="user-rebal-integration",
        display_name="Rebalance Integration User",
        optional_subject="Sociology",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )


@pytest.fixture(scope="module")
def rebal_confidences() -> list[TopicConfidence]:
    return [
        TopicConfidence(
            user_id="user-rebal-integration", subject=s, perceived_confidence=2.0
        )
        for s in [
            Subject.HISTORY,
            Subject.ECONOMY,
            Subject.POLITY,
            Subject.ENVIRONMENT,
            Subject.GEOGRAPHY,
            Subject.SCI_TECH,
        ]
    ]


@pytest.fixture(scope="module")
def base_plan(rebal_profile, rebal_confidences) -> WeeklyPlan:
    """Generate a real plan via Nova 2 Lite, then simulate missed days."""
    plan = generate_plan(
        profile=rebal_profile,
        confidences=rebal_confidences,
        week_start=_WEEK_START,
    )
    assert len(plan.days) == 7

    # Monday (day 0): mark all cards DONE — frozen
    for card in plan.days[0].cards:
        card.status = CheckInStatus.DONE
    plan.days[0].finalized = True

    # Tuesday (day 1): mark all cards SKIPPED — missed
    for card in plan.days[1].cards:
        card.status = CheckInStatus.SKIPPED
    plan.days[1].finalized = True

    # Wednesday (day 2): leave all PENDING — missed (past, untouched)
    # Thursday-Sunday (days 3-6): leave all PENDING — eligible for recovery

    return plan


@pytest.fixture(scope="module")
def rebalanced(base_plan, rebal_profile, rebal_confidences):
    """Call rebalance_plan once, share across all tests."""
    updated_plan, missed_dates, recovery_dates = rebalance_plan(
        plan=base_plan,
        profile=rebal_profile,
        confidences=rebal_confidences,
        recovery_window_days=4,
        today=_TODAY,
    )
    return updated_plan, missed_dates, recovery_dates


@pytest.mark.integration
@skip_no_creds
class TestRebalanceIntegration:

    def test_returns_valid_plan(self, rebal_profile, rebalanced):
        """Rebalanced plan passes full validation."""
        updated_plan, _, _ = rebalanced
        assert isinstance(updated_plan, WeeklyPlan)

        phase = determine_phase(
            prelims_date=rebal_profile.prelims_date,
            mains_date=rebal_profile.mains_date,
            prelims_cleared=rebal_profile.prelims_cleared,
            today=_TODAY,
        )
        result = validate_weekly_plan(updated_plan, rebal_profile, phase)
        assert result.valid, (
            f"Validation failed: {[v.message for v in result.violations if v.severity == 'error']}"
        )

    def test_plan_still_has_7_days(self, rebalanced):
        """Rebalanced plan must still have exactly 7 days."""
        updated_plan, _, _ = rebalanced
        assert len(updated_plan.days) == 7

    def test_missed_dates_correct(self, rebalanced):
        """Tuesday and Wednesday should be identified as missed."""
        _, missed_dates, _ = rebalanced
        assert date(2026, 3, 10) in missed_dates  # Tuesday
        assert date(2026, 3, 11) in missed_dates  # Wednesday
        assert len(missed_dates) == 2

    def test_recovery_dates_correct(self, rebalanced):
        """Thursday through Sunday should be recovery dates."""
        _, _, recovery_dates = rebalanced
        expected = [date(2026, 3, 12), date(2026, 3, 13),
                    date(2026, 3, 14), date(2026, 3, 15)]
        assert recovery_dates == expected

    def test_frozen_day_untouched(self, base_plan, rebalanced):
        """Monday (frozen) should still have all DONE cards."""
        updated_plan, _, _ = rebalanced
        monday = next(d for d in updated_plan.days if d.date == date(2026, 3, 9))
        assert all(c.status == CheckInStatus.DONE for c in monday.cards)

    def test_recovery_days_have_cards(self, rebalanced):
        """Each recovery day should have at least one card."""
        updated_plan, _, recovery_dates = rebalanced
        for rd in recovery_dates:
            day = next(d for d in updated_plan.days if d.date == rd)
            assert len(day.cards) > 0, f"Recovery day {rd} has no cards"

    def test_recovery_days_meet_minimum_minutes(self, rebal_profile, rebalanced):
        """Each recovery day should have at least 85% of daily minutes."""
        updated_plan, _, recovery_dates = rebalanced
        available = int(rebal_profile.available_hours_per_day * 60)
        min_daily = int(available * 0.85)

        for rd in recovery_dates:
            day = next(d for d in updated_plan.days if d.date == rd)
            total = sum(c.planned_duration for c in day.cards)
            assert total >= min_daily, (
                f"Recovery day {rd}: {total}m < minimum {min_daily}m"
            )

    def test_recovery_card_durations_valid(self, rebalanced):
        """Recovery day cards respect block type duration limits."""
        updated_plan, _, recovery_dates = rebalanced
        for rd in recovery_dates:
            day = next(d for d in updated_plan.days if d.date == rd)
            for card in day.cards:
                if card.block_type in _BLOCK_LIMITS:
                    min_dur, max_dur = _BLOCK_LIMITS[card.block_type]
                    assert min_dur <= card.planned_duration <= max_dur, (
                        f"{card.block_type.value} on {rd}: "
                        f"duration {card.planned_duration} outside [{min_dur}, {max_dur}]"
                    )

    def test_fatigue_cap_respected(self, rebal_profile, rebalanced):
        """Each recovery day's total fatigue is within the daily cap."""
        updated_plan, _, recovery_dates = rebalanced
        phase = determine_phase(
            prelims_date=rebal_profile.prelims_date,
            mains_date=rebal_profile.mains_date,
            prelims_cleared=rebal_profile.prelims_cleared,
            today=_TODAY,
        )
        cap = compute_daily_fatigue_cap(rebal_profile.available_hours_per_day, phase)

        for rd in recovery_dates:
            day = next(d for d in updated_plan.days if d.date == rd)
            total_fatigue = sum(c.fatigue for c in day.cards)
            assert total_fatigue <= cap, (
                f"Recovery day {rd}: fatigue {total_fatigue} > cap {cap}"
            )

    def test_r21_ca_integration_max_one(self, rebalanced):
        """Entire week (frozen + recovery) should have at most 1 CA_INTEGRATION."""
        updated_plan, _, _ = rebalanced
        ca_count = sum(
            1
            for day in updated_plan.days
            for card in day.cards
            if card.block_type == BlockType.CA_INTEGRATION
        )
        assert ca_count <= 1, f"CA_INTEGRATION count {ca_count} > 1"

    def test_r13_no_more_than_4_consecutive_heavy(self, rebalanced):
        """No more than 4 consecutive heavy days across the full week."""
        updated_plan, _, _ = rebalanced
        days_sorted = sorted(updated_plan.days, key=lambda d: d.date)
        consecutive = 0
        for day in days_sorted:
            has_heavy = any(c.fatigue >= 3 for c in day.cards)
            if has_heavy:
                consecutive += 1
                assert consecutive <= 4, (
                    f"Day {day.date}: {consecutive} consecutive heavy days (max 4)"
                )
            else:
                consecutive = 0
