"""Integration tests for plan generation — requires AWS creds + Nova 2 Lite access.

Run with: pytest tests/test_planner_integration.py -v -m integration -s

The -s flag shows agent logging output (prompts, retries, violations).
To see detailed agent logs:
    pytest tests/test_planner_integration.py -v -m integration -s --log-cli-level=INFO
"""

from datetime import date

import pytest

from preptrack.agent.planner import generate_plan
from preptrack.engine.phase import determine_phase
from preptrack.engine.validator import validate_weekly_plan
from preptrack.kb import BLOCK_DEFINITIONS
from preptrack.models.enums import Subject
from preptrack.models.plan import WeeklyPlan
from preptrack.models.user import TopicConfidence, UserProfile


def _has_aws_creds() -> bool:
    """Check if AWS credentials are available."""
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

# Build a lookup for block min/max durations
_BLOCK_LIMITS = {
    bd.block_type: (bd.min_duration, bd.max_duration) for bd in BLOCK_DEFINITIONS
}

_WEEK_START = date(2026, 3, 2)


@pytest.fixture(scope="module")
def integration_profile() -> UserProfile:
    return UserProfile(
        user_id="user-integration",
        display_name="Integration Test User",
        optional_subject="Sociology",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )


@pytest.fixture(scope="module")
def integration_confidences() -> list[TopicConfidence]:
    return [
        TopicConfidence(
            user_id="user-integration", subject=s, perceived_confidence=1.0
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
def generated_plan(integration_profile, integration_confidences) -> WeeklyPlan:
    """Call Nova 2 Lite once, share the result across all tests."""
    return generate_plan(
        profile=integration_profile,
        confidences=integration_confidences,
        week_start=_WEEK_START,
    )


@pytest.mark.integration
@skip_no_creds
class TestPlanGenerationIntegration:
    def test_generates_valid_plan(self, integration_profile, generated_plan):
        """generate_plan() returns a WeeklyPlan that passes validation."""
        assert isinstance(generated_plan, WeeklyPlan)

        phase = determine_phase(
            prelims_date=integration_profile.prelims_date,
            mains_date=integration_profile.mains_date,
            prelims_cleared=integration_profile.prelims_cleared,
            today=date.today(),
        )
        result = validate_weekly_plan(generated_plan, integration_profile, phase)
        assert result.valid, (
            f"Validation failed: {[v.message for v in result.violations]}"
        )

    def test_plan_has_7_days(self, generated_plan):
        """Generated plan should have exactly 7 days."""
        assert len(generated_plan.days) == 7

    def test_each_day_has_cards(self, generated_plan):
        """Each day in the plan should have at least one card."""
        for day in generated_plan.days:
            assert len(day.cards) > 0, f"Day {day.date} has no cards"

    def test_card_durations_respect_block_limits(self, generated_plan):
        """Every card's duration should be within its block type's min/max."""
        for day in generated_plan.days:
            for card in day.cards:
                if card.block_type in _BLOCK_LIMITS:
                    min_dur, max_dur = _BLOCK_LIMITS[card.block_type]
                    assert min_dur <= card.planned_duration <= max_dur, (
                        f"Card {card.block_type.value} on {day.date}: "
                        f"duration {card.planned_duration} outside [{min_dur}, {max_dur}]"
                    )
