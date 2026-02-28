"""Unit tests for prompt construction — no LLM calls."""

from datetime import date

import pytest

from preptrack.agent.prompt import build_plan_prompt, build_system_prompt
from preptrack.models.enums import BlockCategory, Phase, Subject
from preptrack.models.plan import SubjectPriority, ValidationViolation
from preptrack.models.user import TopicConfidence, UserProfile


@pytest.fixture
def sample_profile() -> UserProfile:
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
def sample_budgets() -> dict[BlockCategory, int]:
    return {
        BlockCategory.CORE_LEARNING: 150,
        BlockCategory.CORE_RETENTION: 60,
        BlockCategory.CORE_PATTERN: 24,
        BlockCategory.PERFORMANCE: 15,
        BlockCategory.CORRECTIVE: 15,
        BlockCategory.INPUT: 15,
        BlockCategory.PROCESSING: 15,
        BlockCategory.META: 15,
    }


@pytest.fixture
def sample_priorities() -> list[SubjectPriority]:
    return [
        SubjectPriority(
            subject=Subject.HISTORY,
            raw_priority=0.812,
            normalized_confidence=0.2,
            weight=0.203,
            recency_penalty=4.0,
        ),
        SubjectPriority(
            subject=Subject.ECONOMY,
            raw_priority=0.604,
            normalized_confidence=0.4,
            weight=0.189,
            recency_penalty=2.0,
        ),
    ]


@pytest.fixture
def sample_kb_context() -> dict[str, str]:
    return {
        "block_definitions": "# Block Definitions\nDEEP_STUDY: 45-120 min",
        "confidence_model": "# Confidence Model\nStreak bonuses...",
        "engine_reference": "# Engine Reference\nPhase detection...",
        "phase_blueprints": "# Phase Blueprints\nFOUNDATION: 50% Core Learning",
        "rules": "# Rules\nR03: Error Analysis dependency",
        "subject_weights": "# Subject Weights\nHISTORY: 0.203",
    }


# ── System Prompt Tests ─────────────────────────────────────────────


class TestBuildSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_role_description(self):
        prompt = build_system_prompt()
        assert "PrepTrack" in prompt
        assert "UPSC" in prompt

    def test_contains_output_format_instructions(self):
        prompt = build_system_prompt()
        assert "JSON" in prompt

    def test_contains_constraint_references(self):
        prompt = build_system_prompt()
        assert "BlockType" in prompt
        assert "fatigue" in prompt

    def test_mentions_hard_rules(self):
        prompt = build_system_prompt()
        for rule in ["R03", "R04", "R05", "R08", "R09", "R12", "R13"]:
            assert rule in prompt, f"System prompt should mention {rule}"


# ── Plan Prompt Tests ───────────────────────────────────────────────


class TestBuildPlanPrompt:
    def test_includes_profile_data(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        assert "user-test" in prompt
        assert "both" in prompt
        assert "Sociology" in prompt
        assert "2026-05-25" in prompt
        assert "6.0" in prompt

    def test_includes_phase(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.CONSOLIDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        assert "CONSOLIDATION" in prompt

    def test_includes_category_budgets(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        assert "CORE_LEARNING" in prompt
        assert "150" in prompt

    def test_includes_subject_priorities(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        assert "HISTORY" in prompt
        assert "0.812" in prompt
        assert "ECONOMY" in prompt

    def test_includes_week_dates(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        assert "2026-03-02" in prompt
        assert "2026-03-08" in prompt  # Sunday

    def test_includes_all_kb_sections(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        for section_name in sample_kb_context:
            assert section_name in prompt, f"KB section '{section_name}' missing from prompt"

    def test_includes_output_schema(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        assert "block_type" in prompt
        assert "planned_duration" in prompt
        assert "DEEP_STUDY" in prompt

    def test_no_violations_section_on_first_attempt(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
            violations=None,
        )
        assert "REJECTED" not in prompt
        assert "Fix These Violations" not in prompt

    def test_includes_violations_on_retry(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        violations = [
            ValidationViolation(
                rule_id="R08",
                message="Daily fatigue 15 exceeds cap 12",
                day=date(2026, 3, 3),
            ),
            ValidationViolation(
                rule_id="R09",
                message="Core Learning has 3 subjects (max 2)",
                day=date(2026, 3, 4),
            ),
        ]
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
            violations=violations,
        )
        assert "REJECTED" in prompt
        assert "R08" in prompt
        assert "Daily fatigue 15 exceeds cap 12" in prompt
        assert "R09" in prompt
        assert "2026-03-03" in prompt

    def test_empty_priorities_handled(
        self, sample_profile, sample_budgets, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=[],
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        # Should not crash, priorities section just not present
        assert "user-test" in prompt

    def test_available_minutes_calculated(
        self, sample_profile, sample_budgets, sample_priorities, sample_kb_context
    ):
        prompt = build_plan_prompt(
            profile=sample_profile,
            phase=Phase.FOUNDATION,
            category_budgets=sample_budgets,
            subject_priorities=sample_priorities,
            kb_context=sample_kb_context,
            week_start=date(2026, 3, 2),
        )
        assert "360" in prompt  # 6 hours * 60 minutes
