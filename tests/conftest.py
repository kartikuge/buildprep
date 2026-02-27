from datetime import date, datetime

import pytest

from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    CheckInStatus,
    HeavyLevel,
    MainsPaper,
    Phase,
    Subject,
)
from preptrack.models.kb import (
    BlockDefinition,
    CategoryAllocation,
    ConfidenceConfig,
    PhaseBlueprint,
    SubjectWeight,
)
from preptrack.models.plan import DailyPlan, PlanCard, WeeklyPlan
from preptrack.models.user import TopicConfidence, UserProfile

from preptrack.kb import (
    BLOCK_DEFINITIONS,
    CONFIDENCE_CONFIG,
    PHASE_BLUEPRINTS,
    SUBJECT_WEIGHTS,
)


# ── KB Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def subject_weights() -> list[SubjectWeight]:
    return SUBJECT_WEIGHTS


@pytest.fixture
def confidence_config() -> ConfidenceConfig:
    return CONFIDENCE_CONFIG


@pytest.fixture
def phase_blueprints() -> dict[Phase, PhaseBlueprint]:
    return PHASE_BLUEPRINTS


@pytest.fixture
def block_definitions() -> list[BlockDefinition]:
    return BLOCK_DEFINITIONS


# ── Test Users ───────────────────────────────────────────────────────


@pytest.fixture
def fresh_user() -> UserProfile:
    return UserProfile(
        user_id="user-fresh",
        display_name="Fresh Beginner",
        optional_subject="Sociology",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
        created_at=datetime(2026, 1, 1),
    )


@pytest.fixture
def intermediate_user() -> UserProfile:
    return UserProfile(
        user_id="user-intermediate",
        display_name="Intermediate Aspirant",
        optional_subject="PSIR",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=5.0,
        created_at=datetime(2025, 6, 1),
    )


@pytest.fixture
def working_pro_user() -> UserProfile:
    return UserProfile(
        user_id="user-workpro",
        display_name="Working Professional",
        optional_subject=None,
        stage="prelims",
        prelims_date=date(2026, 5, 25),
        available_hours_per_day=2.5,
        created_at=datetime(2026, 2, 1),
    )


# ── Confidence Fixtures ──────────────────────────────────────────────


@pytest.fixture
def fresh_confidences() -> list[TopicConfidence]:
    """All subjects at confidence 1.0, no history."""
    return [
        TopicConfidence(user_id="user-fresh", subject=s, perceived_confidence=1.0)
        for s in [Subject.HISTORY, Subject.ECONOMY, Subject.POLITY,
                  Subject.ENVIRONMENT, Subject.GEOGRAPHY, Subject.SCI_TECH]
    ]


@pytest.fixture
def varied_confidences() -> list[TopicConfidence]:
    """Varied confidences for intermediate user."""
    today = date(2026, 2, 25)
    return [
        TopicConfidence(user_id="user-intermediate", subject=Subject.HISTORY, perceived_confidence=3.5, streak=8, total_sessions=15, last_practiced_date=today),
        TopicConfidence(user_id="user-intermediate", subject=Subject.ECONOMY, perceived_confidence=2.0, streak=0, skip_count=4, total_sessions=8, last_practiced_date=date(2026, 2, 18)),
        TopicConfidence(user_id="user-intermediate", subject=Subject.POLITY, perceived_confidence=4.0, streak=12, total_sessions=22, last_practiced_date=today),
        TopicConfidence(user_id="user-intermediate", subject=Subject.ENVIRONMENT, perceived_confidence=1.5, streak=0, skip_count=2, total_sessions=5, last_practiced_date=date(2026, 2, 10)),
        TopicConfidence(user_id="user-intermediate", subject=Subject.GEOGRAPHY, perceived_confidence=2.8, streak=3, total_sessions=12, last_practiced_date=date(2026, 2, 22)),
        TopicConfidence(user_id="user-intermediate", subject=Subject.SCI_TECH, perceived_confidence=1.2, streak=0, total_sessions=3, last_practiced_date=date(2026, 2, 5)),
    ]


# ── Helper to build daily plans ─────────────────────────────────────


def make_card(
    block_type: BlockType = BlockType.REVISION,
    category: BlockCategory = BlockCategory.CORE_RETENTION,
    subject: Subject | None = Subject.HISTORY,
    fatigue: int = 1,
    duration: int = 45,
    order: int = 0,
) -> PlanCard:
    return PlanCard(
        block_type=block_type,
        category=category,
        subject=subject,
        topic="Test Topic",
        planned_duration=duration,
        fatigue=fatigue,
        order=order,
    )


def make_daily(d: date, cards: list[PlanCard]) -> DailyPlan:
    return DailyPlan(date=d, cards=cards)


def make_weekly(user_id: str, week_start: date, days: list[DailyPlan]) -> WeeklyPlan:
    return WeeklyPlan(user_id=user_id, week_start=week_start, days=days)
