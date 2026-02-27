from datetime import date, timedelta

import pytest

from preptrack.engine.validator import validate_weekly_plan
from preptrack.models.enums import (
    BlockCategory,
    BlockType,
    Phase,
    Subject,
)
from preptrack.models.plan import DailyPlan, PlanCard, WeeklyPlan
from preptrack.models.user import UserProfile
from tests.conftest import make_card, make_daily, make_weekly


MON = date(2026, 3, 2)


def _user(hours: float = 6.0) -> UserProfile:
    return UserProfile(
        user_id="test", display_name="Test", stage="both",
        prelims_date=date(2026, 5, 25), available_hours_per_day=hours,
    )


class TestR03ErrorAnalysisDependency:
    def test_ea_with_mcq_same_day_passes(self):
        day = make_daily(MON, [
            make_card(BlockType.TIMED_MCQ, BlockCategory.PERFORMANCE, fatigue=3, duration=60),
            make_card(BlockType.ERROR_ANALYSIS, BlockCategory.CORRECTIVE, fatigue=3, duration=45),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r03 = [v for v in result.violations if v.rule_id == "R03"]
        assert len(r03) == 0

    def test_ea_with_mock_previous_day_passes(self):
        day1 = make_daily(MON, [
            make_card(BlockType.FULL_MOCK, BlockCategory.PERFORMANCE, fatigue=4, duration=120),
        ])
        day2 = make_daily(MON + timedelta(days=1), [
            make_card(BlockType.ERROR_ANALYSIS, BlockCategory.CORRECTIVE, fatigue=3, duration=45),
        ])
        plan = make_weekly("test", MON, [day1, day2])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r03 = [v for v in result.violations if v.rule_id == "R03"]
        assert len(r03) == 0

    def test_ea_standalone_fails(self):
        day = make_daily(MON, [
            make_card(BlockType.ERROR_ANALYSIS, BlockCategory.CORRECTIVE, fatigue=3, duration=45),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r03 = [v for v in result.violations if v.rule_id == "R03"]
        assert len(r03) == 1


class TestR04ConsolidationDay:
    def test_consolidation_day_light_only_passes(self):
        day = make_daily(MON, [
            make_card(BlockType.CONSOLIDATION_DAY, BlockCategory.RETENTION, fatigue=1, duration=180),
            make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, fatigue=1, duration=60),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.PRELIMS_SPRINT_75)
        r04 = [v for v in result.violations if v.rule_id == "R04"]
        assert len(r04) == 0

    def test_consolidation_day_with_heavy_fails(self):
        day = make_daily(MON, [
            make_card(BlockType.CONSOLIDATION_DAY, BlockCategory.RETENTION, fatigue=1, duration=180),
            make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, fatigue=3, duration=90),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.PRELIMS_SPRINT_75)
        r04 = [v for v in result.violations if v.rule_id == "R04"]
        assert len(r04) == 1


class TestR05FullMockIsolation:
    def test_mock_alone_passes(self):
        day = make_daily(MON, [
            make_card(BlockType.FULL_MOCK, BlockCategory.PERFORMANCE, fatigue=4, duration=120),
            make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, fatigue=1, duration=30),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r05 = [v for v in result.violations if v.rule_id == "R05"]
        assert len(r05) == 0

    def test_mock_with_heavy_fails(self):
        day = make_daily(MON, [
            make_card(BlockType.FULL_MOCK, BlockCategory.PERFORMANCE, fatigue=4, duration=120),
            make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, fatigue=3, duration=90),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r05 = [v for v in result.violations if v.rule_id == "R05"]
        assert len(r05) == 1

    def test_back_to_back_mock_days_fails(self):
        day1 = make_daily(MON, [
            make_card(BlockType.FULL_MOCK, BlockCategory.PERFORMANCE, fatigue=4, duration=120),
        ])
        day2 = make_daily(MON + timedelta(days=1), [
            make_card(BlockType.FULL_MOCK, BlockCategory.PERFORMANCE, fatigue=4, duration=120),
        ])
        plan = make_weekly("test", MON, [day1, day2])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r05 = [v for v in result.violations if v.rule_id == "R05"]
        assert len(r05) >= 1

    def test_two_mocks_same_day_fails(self):
        day = make_daily(MON, [
            make_card(BlockType.FULL_MOCK, BlockCategory.PERFORMANCE, fatigue=4, duration=120),
            make_card(BlockType.FULL_MOCK, BlockCategory.PERFORMANCE, fatigue=4, duration=120),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r05 = [v for v in result.violations if v.rule_id == "R05"]
        assert len(r05) >= 1


class TestR08DailyFatigueCap:
    def test_within_cap_passes(self):
        day = make_daily(MON, [
            make_card(fatigue=3, duration=90),
            make_card(fatigue=3, duration=90),
            make_card(fatigue=3, duration=60),
            make_card(fatigue=1, duration=30),
        ])
        plan = make_weekly("test", MON, [day])
        # 6 hrs × 2 = 12 cap; fatigue = 10 → pass
        result = validate_weekly_plan(plan, _user(6.0), Phase.FOUNDATION)
        r08 = [v for v in result.violations if v.rule_id == "R08"]
        assert len(r08) == 0

    def test_exceeds_cap_fails(self):
        day = make_daily(MON, [
            make_card(fatigue=4, duration=120),
            make_card(fatigue=4, duration=120),
            make_card(fatigue=3, duration=90),
            make_card(fatigue=3, duration=30),
        ])
        plan = make_weekly("test", MON, [day])
        # 3 hrs × 2 = 6 cap; fatigue = 14 → fail
        result = validate_weekly_plan(plan, _user(3.0), Phase.FOUNDATION)
        r08 = [v for v in result.violations if v.rule_id == "R08"]
        assert len(r08) == 1


class TestR09TopicDiversity:
    def test_two_cl_subjects_passes(self):
        day = make_daily(MON, [
            make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, Subject.HISTORY, fatigue=3, duration=90),
            make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, Subject.ECONOMY, fatigue=3, duration=90),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r09 = [v for v in result.violations if v.rule_id == "R09"]
        assert len(r09) == 0

    def test_three_cl_subjects_fails(self):
        day = make_daily(MON, [
            make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, Subject.HISTORY, fatigue=3, duration=60),
            make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, Subject.ECONOMY, fatigue=3, duration=60),
            make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, Subject.POLITY, fatigue=3, duration=60),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r09 = [v for v in result.violations if v.rule_id == "R09"]
        assert len(r09) == 1

    def test_four_cr_subjects_passes(self):
        day = make_daily(MON, [
            make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, Subject.HISTORY, fatigue=1, duration=30),
            make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, Subject.ECONOMY, fatigue=1, duration=30),
            make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, Subject.POLITY, fatigue=1, duration=30),
            make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, Subject.GEOGRAPHY, fatigue=1, duration=30),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r09 = [v for v in result.violations if v.rule_id == "R09"]
        assert len(r09) == 0


class TestR12WorkingProfessionalGuard:
    def test_one_heavy_passes(self):
        day = make_daily(MON, [
            make_card(fatigue=3, duration=60),
            make_card(fatigue=1, duration=60),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(2.5), Phase.FOUNDATION)
        r12 = [v for v in result.violations if v.rule_id == "R12"]
        assert len(r12) == 0

    def test_two_heavy_fails_for_low_hours(self):
        day = make_daily(MON, [
            make_card(fatigue=3, duration=45),
            make_card(fatigue=3, duration=45),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(2.5), Phase.FOUNDATION)
        r12 = [v for v in result.violations if v.rule_id == "R12"]
        assert len(r12) == 1

    def test_two_heavy_ok_for_high_hours(self):
        day = make_daily(MON, [
            make_card(fatigue=3, duration=90),
            make_card(fatigue=3, duration=90),
        ])
        plan = make_weekly("test", MON, [day])
        result = validate_weekly_plan(plan, _user(6.0), Phase.FOUNDATION)
        r12 = [v for v in result.violations if v.rule_id == "R12"]
        assert len(r12) == 0


class TestR13BurnoutPrevention:
    def test_four_consecutive_heavy_passes(self):
        days = []
        for i in range(4):
            days.append(make_daily(MON + timedelta(days=i), [
                make_card(fatigue=3, duration=90),
            ]))
        plan = make_weekly("test", MON, days)
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r13 = [v for v in result.violations if v.rule_id == "R13"]
        assert len(r13) == 0

    def test_five_consecutive_heavy_fails(self):
        days = []
        for i in range(5):
            days.append(make_daily(MON + timedelta(days=i), [
                make_card(fatigue=3, duration=90),
            ]))
        plan = make_weekly("test", MON, days)
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r13 = [v for v in result.violations if v.rule_id == "R13"]
        assert len(r13) == 1

    def test_light_day_resets_counter(self):
        days = []
        for i in range(4):
            days.append(make_daily(MON + timedelta(days=i), [
                make_card(fatigue=3, duration=90),
            ]))
        # Day 5: light only
        days.append(make_daily(MON + timedelta(days=4), [
            make_card(fatigue=1, duration=60),
        ]))
        # Day 6-7: heavy again
        for i in range(5, 7):
            days.append(make_daily(MON + timedelta(days=i), [
                make_card(fatigue=3, duration=90),
            ]))
        plan = make_weekly("test", MON, days)
        result = validate_weekly_plan(plan, _user(), Phase.FOUNDATION)
        r13 = [v for v in result.violations if v.rule_id == "R13"]
        assert len(r13) == 0


class TestValidPlan:
    def test_valid_plan_passes_all(self):
        """A well-formed plan should pass all validators."""
        days = [
            make_daily(MON, [
                make_card(BlockType.DEEP_STUDY, BlockCategory.CORE_LEARNING, Subject.HISTORY, fatigue=3, duration=90),
                make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, Subject.ECONOMY, fatigue=1, duration=45),
                make_card(BlockType.QUICK_RECALL, BlockCategory.CORE_RETENTION, Subject.POLITY, fatigue=1, duration=20),
            ]),
            make_daily(MON + timedelta(days=1), [
                make_card(BlockType.STUDY_LIGHT, BlockCategory.CORE_LEARNING, Subject.GEOGRAPHY, fatigue=2, duration=60),
                make_card(BlockType.PYQ_ANALYSIS, BlockCategory.CORE_PATTERN, Subject.HISTORY, fatigue=2, duration=60),
            ]),
            make_daily(MON + timedelta(days=2), [
                make_card(BlockType.TIMED_MCQ, BlockCategory.PERFORMANCE, Subject.ECONOMY, fatigue=3, duration=60),
                make_card(BlockType.ERROR_ANALYSIS, BlockCategory.CORRECTIVE, Subject.ECONOMY, fatigue=3, duration=45),
            ]),
            # Light day after 3 heavy days
            make_daily(MON + timedelta(days=3), [
                make_card(BlockType.REVISION, BlockCategory.CORE_RETENTION, Subject.POLITY, fatigue=1, duration=45),
                make_card(BlockType.QUICK_RECALL, BlockCategory.CORE_RETENTION, Subject.ENVIRONMENT, fatigue=1, duration=20),
            ]),
        ]
        plan = make_weekly("test", MON, days)
        result = validate_weekly_plan(plan, _user(6.0), Phase.FOUNDATION)
        assert result.valid, f"Violations: {[v.message for v in result.violations]}"
