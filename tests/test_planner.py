"""Unit tests for planner with mocked LLM — no AWS creds needed."""

from datetime import date
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from preptrack.agent.exceptions import PlanGenerationError
from preptrack.agent.planner import (
    MAX_RETRIES,
    _call_llm,
    _compute_context,
    _extract_json,
    _next_monday,
    _repair_r13,
    generate_plan,
)
from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    Phase,
    Subject,
)
from preptrack.models.plan import (
    DailyPlan,
    PlanCard,
    SubjectPriority,
    ValidationResult,
    ValidationViolation,
    WeeklyPlan,
)
from preptrack.models.user import TopicConfidence, UserProfile


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def profile() -> UserProfile:
    return UserProfile(
        user_id="user-test",
        display_name="Test User",
        optional_subject="Sociology",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=6.0,
    )


@pytest.fixture
def confidences() -> list[TopicConfidence]:
    return [
        TopicConfidence(user_id="user-test", subject=s, perceived_confidence=1.0)
        for s in [
            Subject.HISTORY, Subject.ECONOMY, Subject.POLITY,
            Subject.ENVIRONMENT, Subject.GEOGRAPHY, Subject.SCI_TECH,
        ]
    ]


def _make_valid_weekly_plan(user_id: str, week_start: date) -> WeeklyPlan:
    """Build a minimal valid weekly plan for testing."""
    days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        cards = [
            PlanCard(
                block_type=BlockType.REVISION,
                category=BlockCategory.CORE_RETENTION,
                subject=Subject.HISTORY,
                topic="Ancient India - Indus Valley",
                planned_duration=45,
                fatigue=1,
                order=0,
            ),
            PlanCard(
                block_type=BlockType.QUICK_RECALL,
                category=BlockCategory.CORE_RETENTION,
                subject=Subject.POLITY,
                topic="Fundamental Rights",
                planned_duration=15,
                fatigue=1,
                order=1,
            ),
        ]
        days.append(DailyPlan(date=d, cards=cards))
    return WeeklyPlan(
        user_id=user_id,
        week_start=week_start,
        days=days,
        narrative="Test narrative",
    )


# ── Helper Tests ────────────────────────────────────────────────────


class TestNextMonday:
    def test_monday_returns_same(self):
        monday = date(2026, 3, 2)  # Monday
        assert _next_monday(monday) == monday

    def test_tuesday_returns_next_monday(self):
        tuesday = date(2026, 3, 3)
        assert _next_monday(tuesday) == date(2026, 3, 9)

    def test_sunday_returns_next_monday(self):
        sunday = date(2026, 3, 8)
        assert _next_monday(sunday) == date(2026, 3, 9)

    def test_saturday_returns_next_monday(self):
        saturday = date(2026, 3, 7)
        assert _next_monday(saturday) == date(2026, 3, 9)


class TestExtractJson:
    def test_plain_json(self):
        text = '{"user_id": "test", "week_start": "2026-03-02"}'
        assert _extract_json(text) is not None

    def test_json_in_code_fence(self):
        text = '```json\n{"user_id": "test"}\n```'
        result = _extract_json(text)
        assert result is not None
        assert '"user_id"' in result

    def test_json_in_bare_fence(self):
        text = '```\n{"user_id": "test"}\n```'
        result = _extract_json(text)
        assert result is not None

    def test_no_json(self):
        assert _extract_json("no json here") is None

    def test_json_with_surrounding_text(self):
        text = 'Here is the plan:\n{"user_id": "test"}\nDone!'
        assert _extract_json(text) is not None


# ── Deterministic Context Tests ─────────────────────────────────────


class TestComputeContext:
    def test_returns_phase_budgets_priorities(self, profile, confidences):
        phase, budgets, priorities = _compute_context(
            profile=profile,
            confidences=confidences,
            previous_phase=None,
            days_in_phase=30,
            today=date(2026, 2, 26),
        )
        assert isinstance(phase, Phase)
        assert isinstance(budgets, dict)
        assert all(isinstance(k, BlockCategory) for k in budgets)
        assert all(isinstance(v, int) for v in budgets.values())
        assert isinstance(priorities, list)
        assert all(isinstance(p, SubjectPriority) for p in priorities)

    def test_phase_detection_foundation(self, profile, confidences):
        """Far from prelims → FOUNDATION."""
        phase, _, _ = _compute_context(
            profile=profile,
            confidences=confidences,
            previous_phase=None,
            days_in_phase=30,
            today=date(2025, 6, 1),
        )
        assert phase == Phase.FOUNDATION

    def test_phase_detection_prelims_sprint(self, profile, confidences):
        """Close to prelims → PRELIMS_SPRINT_75."""
        phase, _, _ = _compute_context(
            profile=profile,
            confidences=confidences,
            previous_phase=None,
            days_in_phase=30,
            today=date(2026, 4, 1),
        )
        assert phase == Phase.PRELIMS_SPRINT_75

    def test_budgets_sum_to_available(self, profile, confidences):
        """Budget minutes should sum to available - news time."""
        _, budgets, _ = _compute_context(
            profile=profile,
            confidences=confidences,
            previous_phase=None,
            days_in_phase=30,
            today=date(2026, 2, 26),
        )
        total = sum(budgets.values())
        # available = 360 min, minus 20 news = 340
        assert total == 340

    def test_priorities_sorted_descending(self, profile, confidences):
        """Subject priorities should be ranked by raw_priority descending."""
        _, _, priorities = _compute_context(
            profile=profile,
            confidences=confidences,
            previous_phase=None,
            days_in_phase=30,
            today=date(2026, 2, 26),
        )
        for i in range(len(priorities) - 1):
            assert priorities[i].raw_priority >= priorities[i + 1].raw_priority


# ── Generate Plan Tests (Mocked LLM) ───────────────────────────────


class TestGeneratePlan:
    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_valid_plan_returned_first_attempt(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """Mock LLM returns a valid plan → generate_plan returns it."""
        week_start = date(2026, 3, 2)
        valid_plan = _make_valid_weekly_plan("user-test", week_start)
        mock_call_llm.return_value = valid_plan

        result = generate_plan(
            profile=profile,
            confidences=confidences,
            week_start=week_start,
        )

        assert result == valid_plan
        assert mock_call_llm.call_count == 1

    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_retry_on_validation_failure(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """Mock returns invalid plan first, valid plan second → retry works."""
        week_start = date(2026, 3, 2)
        valid_plan = _make_valid_weekly_plan("user-test", week_start)

        # Invalid plan: violates R09 (3 Core Learning subjects on day 1)
        invalid_plan = _make_valid_weekly_plan("user-test", week_start)
        invalid_plan.days[0].cards.extend([
            PlanCard(
                block_type=BlockType.STUDY_LIGHT,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.HISTORY,
                topic="Test",
                planned_duration=45,
                fatigue=2,
                order=2,
            ),
            PlanCard(
                block_type=BlockType.STUDY_LIGHT,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.ECONOMY,
                topic="Test",
                planned_duration=45,
                fatigue=2,
                order=3,
            ),
            PlanCard(
                block_type=BlockType.STUDY_LIGHT,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.POLITY,
                topic="Test",
                planned_duration=45,
                fatigue=2,
                order=4,
            ),
        ])

        mock_call_llm.side_effect = [invalid_plan, valid_plan]

        result = generate_plan(
            profile=profile,
            confidences=confidences,
            week_start=week_start,
        )

        assert result == valid_plan
        assert mock_call_llm.call_count == 2

    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_raises_after_max_retries(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """Mock always returns invalid → PlanGenerationError after MAX_RETRIES."""
        week_start = date(2026, 3, 2)

        # Plan that violates R09: 3 Core Learning subjects on same day (max 2)
        invalid_plan = _make_valid_weekly_plan("user-test", week_start)
        invalid_plan.days[0].cards.extend([
            PlanCard(
                block_type=BlockType.STUDY_LIGHT,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.HISTORY,
                topic="Test",
                planned_duration=45,
                fatigue=2,
                order=2,
            ),
            PlanCard(
                block_type=BlockType.STUDY_LIGHT,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.ECONOMY,
                topic="Test",
                planned_duration=45,
                fatigue=2,
                order=3,
            ),
            PlanCard(
                block_type=BlockType.STUDY_LIGHT,
                category=BlockCategory.CORE_LEARNING,
                subject=Subject.POLITY,
                topic="Test",
                planned_duration=45,
                fatigue=2,
                order=4,
            ),
        ])

        mock_call_llm.return_value = invalid_plan

        with pytest.raises(PlanGenerationError) as exc_info:
            generate_plan(
                profile=profile,
                confidences=confidences,
                week_start=week_start,
            )

        assert len(exc_info.value.violations) > 0
        assert mock_call_llm.call_count == MAX_RETRIES

    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_retry_on_none_response(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """Mock returns None first (parse failure), valid plan second → retry works."""
        week_start = date(2026, 3, 2)
        valid_plan = _make_valid_weekly_plan("user-test", week_start)

        mock_call_llm.side_effect = [None, valid_plan]

        result = generate_plan(
            profile=profile,
            confidences=confidences,
            week_start=week_start,
        )

        assert result == valid_plan
        assert mock_call_llm.call_count == 2

    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_raises_after_all_none_responses(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """Mock always returns None → PlanGenerationError after MAX_RETRIES."""
        week_start = date(2026, 3, 2)
        mock_call_llm.return_value = None

        with pytest.raises(PlanGenerationError):
            generate_plan(
                profile=profile,
                confidences=confidences,
                week_start=week_start,
            )

        assert mock_call_llm.call_count == MAX_RETRIES

    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_agent_initialized_with_system_prompt(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """Verify Agent is created with system_prompt and model."""
        week_start = date(2026, 3, 2)
        valid_plan = _make_valid_weekly_plan("user-test", week_start)
        mock_call_llm.return_value = valid_plan

        generate_plan(
            profile=profile,
            confidences=confidences,
            week_start=week_start,
        )

        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args[1]
        assert "system_prompt" in call_kwargs
        assert "model" in call_kwargs
        assert "PrepTrack" in call_kwargs["system_prompt"]

    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_default_week_start_is_next_monday(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """When week_start is None, defaults to next Monday."""
        valid_plan = _make_valid_weekly_plan("user-test", date(2026, 3, 2))
        mock_call_llm.return_value = valid_plan

        with patch("preptrack.agent.planner.validate_weekly_plan") as mock_validate:
            mock_validate.return_value = ValidationResult(valid=True)
            generate_plan(profile=profile, confidences=confidences)

        assert mock_call_llm.call_count == 1

    @patch("preptrack.agent.planner._call_llm")
    @patch("preptrack.agent.planner.Agent")
    @patch("preptrack.agent.planner.BedrockModel")
    def test_bedrock_model_configured(
        self, mock_bedrock_cls, mock_agent_cls, mock_call_llm, profile, confidences
    ):
        """Verify BedrockModel is configured with correct model_id and region."""
        week_start = date(2026, 3, 2)
        valid_plan = _make_valid_weekly_plan("user-test", week_start)
        mock_call_llm.return_value = valid_plan

        generate_plan(
            profile=profile,
            confidences=confidences,
            week_start=week_start,
            model_id="us.amazon.nova-2-lite-v1:0",
            region="us-west-2",
        )

        mock_bedrock_cls.assert_called_once_with(
            model_id="us.amazon.nova-2-lite-v1:0",
            region_name="us-west-2",
            temperature=0.3,
            max_tokens=5120,
        )


# ── _call_llm Tests ─────────────────────────────────────────────────


class TestCallLlm:
    def test_parses_valid_json_response(self):
        """Agent returns valid JSON text → parsed into WeeklyPlan."""
        week_start = date(2026, 3, 2)
        valid_plan = _make_valid_weekly_plan("user-test", week_start)

        mock_result = MagicMock()
        mock_result.__str__ = lambda self: valid_plan.model_dump_json()
        mock_agent = MagicMock()
        mock_agent.return_value = mock_result

        result = _call_llm(mock_agent, "test prompt")
        assert result is not None
        assert isinstance(result, WeeklyPlan)
        assert len(result.days) == 7
        mock_agent.assert_called_once()

    def test_parses_json_in_code_fence(self):
        """Agent returns JSON wrapped in markdown code fence → still parsed."""
        week_start = date(2026, 3, 2)
        valid_plan = _make_valid_weekly_plan("user-test", week_start)

        mock_result = MagicMock()
        mock_result.__str__ = lambda self: f"```json\n{valid_plan.model_dump_json()}\n```"
        mock_agent = MagicMock()
        mock_agent.return_value = mock_result

        result = _call_llm(mock_agent, "test prompt")
        assert result is not None
        assert isinstance(result, WeeklyPlan)

    def test_returns_none_on_exception(self):
        """Agent raises exception → returns None."""
        mock_agent = MagicMock()
        mock_agent.side_effect = Exception("LLM unavailable")

        result = _call_llm(mock_agent, "test prompt")
        assert result is None

    def test_returns_none_on_non_json_response(self):
        """Agent returns text with no JSON → returns None."""
        mock_result = MagicMock()
        mock_result.__str__ = lambda self: "I cannot generate a plan right now."
        mock_agent = MagicMock()
        mock_agent.return_value = mock_result

        result = _call_llm(mock_agent, "test prompt")
        assert result is None


# ── _repair_r13 Tests ───────────────────────────────────────────────


class TestRepairR13:
    def test_no_repair_needed(self):
        """Plan with no R13 violations is returned unchanged."""
        week_start = date(2026, 3, 2)
        plan = _make_valid_weekly_plan("user-test", week_start)
        # All cards are fatigue=1, no heavy days at all
        repaired = _repair_r13(plan)
        for day in repaired.days:
            for card in day.cards:
                assert card.block_type in (BlockType.REVISION, BlockType.QUICK_RECALL)

    def test_four_heavy_days_no_repair(self):
        """Exactly 4 consecutive heavy days is fine — no repair needed."""
        week_start = date(2026, 3, 2)
        plan = _make_valid_weekly_plan("user-test", week_start)
        # Add heavy block to first 4 days only
        for day in plan.days[:4]:
            day.cards.append(
                PlanCard(
                    block_type=BlockType.DEEP_STUDY,
                    category=BlockCategory.CORE_LEARNING,
                    subject=Subject.HISTORY,
                    topic="Test Heavy",
                    planned_duration=60,
                    fatigue=3,
                    order=2,
                )
            )
        repaired = _repair_r13(plan)
        # Days 0-3 should still have DEEP_STUDY
        for day in repaired.days[:4]:
            heavy_cards = [c for c in day.cards if c.fatigue >= 3]
            assert len(heavy_cards) == 1

    def test_five_heavy_days_repairs_day_5(self):
        """5 consecutive heavy days → day 5 gets downgraded."""
        week_start = date(2026, 3, 2)
        plan = _make_valid_weekly_plan("user-test", week_start)
        for day in plan.days[:5]:
            day.cards.append(
                PlanCard(
                    block_type=BlockType.DEEP_STUDY,
                    category=BlockCategory.CORE_LEARNING,
                    subject=Subject.HISTORY,
                    topic="Test Heavy",
                    planned_duration=60,
                    fatigue=3,
                    order=2,
                )
            )
        repaired = _repair_r13(plan)
        # Day 5 (index 4) should have no heavy cards after repair
        day5_heavy = [c for c in repaired.days[4].cards if c.fatigue >= 3]
        assert len(day5_heavy) == 0

    def test_seven_heavy_days_repairs_correctly(self):
        """All 7 days heavy → days 5 and 7 get downgraded (resets after each repair)."""
        week_start = date(2026, 3, 2)
        plan = _make_valid_weekly_plan("user-test", week_start)
        for day in plan.days:
            day.cards.append(
                PlanCard(
                    block_type=BlockType.DEEP_STUDY,
                    category=BlockCategory.CORE_LEARNING,
                    subject=Subject.HISTORY,
                    topic="Test Heavy",
                    planned_duration=60,
                    fatigue=3,
                    order=2,
                )
            )
        repaired = _repair_r13(plan)
        # After repair, no day should have 5+ consecutive heavy
        consecutive = 0
        for day in sorted(repaired.days, key=lambda d: d.date):
            if any(c.fatigue >= 3 for c in day.cards):
                consecutive += 1
            else:
                consecutive = 0
            assert consecutive <= 4

    def test_repair_preserves_subject_and_topic(self):
        """Repaired cards keep original subject and topic."""
        week_start = date(2026, 3, 2)
        plan = _make_valid_weekly_plan("user-test", week_start)
        for day in plan.days[:5]:
            day.cards.append(
                PlanCard(
                    block_type=BlockType.DEEP_STUDY,
                    category=BlockCategory.CORE_LEARNING,
                    subject=Subject.ECONOMY,
                    topic="Fiscal Policy",
                    planned_duration=60,
                    fatigue=3,
                    order=2,
                )
            )
        repaired = _repair_r13(plan)
        # The repaired card on day 5 should still reference ECONOMY
        repaired_card = repaired.days[4].cards[2]  # the appended card
        assert repaired_card.subject == Subject.ECONOMY
        assert repaired_card.topic == "Fiscal Policy"

    def test_repair_uses_correct_replacement_types(self):
        """DEEP_STUDY → REVISION, TIMED_MCQ → PYQ_ANALYSIS."""
        week_start = date(2026, 3, 2)
        plan = _make_valid_weekly_plan("user-test", week_start)
        for day in plan.days[:5]:
            day.cards.append(
                PlanCard(
                    block_type=BlockType.TIMED_MCQ,
                    category=BlockCategory.PERFORMANCE,
                    subject=Subject.POLITY,
                    topic="Test MCQ",
                    planned_duration=60,
                    fatigue=3,
                    order=2,
                )
            )
        repaired = _repair_r13(plan)
        repaired_card = repaired.days[4].cards[2]
        assert repaired_card.block_type == BlockType.PYQ_ANALYSIS
        assert repaired_card.fatigue <= 2
