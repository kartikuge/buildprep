from datetime import timedelta

from preptrack.models.enums import BlockCategory, BlockType, Phase
from preptrack.models.plan import (
    DailyPlan,
    PlanCard,
    ValidationResult,
    ValidationViolation,
    WeeklyPlan,
)
from preptrack.models.user import UserProfile
from preptrack.engine.fatigue import compute_daily_fatigue_cap


# Block types that trigger Error Analysis requirement
_EA_TRIGGERS = {BlockType.FULL_MOCK, BlockType.TIMED_MCQ, BlockType.PYQ_ANALYSIS}


def _has_block_type(cards: list[PlanCard], bt: BlockType) -> bool:
    return any(c.block_type == bt for c in cards)


def _validate_r03(plan: WeeklyPlan) -> list[ValidationViolation]:
    """R03: Error Analysis must follow mock/MCQ/PYQ same or next day."""
    violations: list[ValidationViolation] = []
    days_sorted = sorted(plan.days, key=lambda d: d.date)
    day_map = {d.date: d for d in days_sorted}

    for day in days_sorted:
        if not _has_block_type(day.cards, BlockType.ERROR_ANALYSIS):
            continue
        prev_date = day.date - timedelta(days=1)
        has_trigger_today = any(c.block_type in _EA_TRIGGERS for c in day.cards)
        has_trigger_yesterday = (
            prev_date in day_map
            and any(c.block_type in _EA_TRIGGERS for c in day_map[prev_date].cards)
        )
        if not has_trigger_today and not has_trigger_yesterday:
            violations.append(
                ValidationViolation(
                    rule_id="R03",
                    message="Error Analysis without preceding mock/MCQ/PYQ",
                    day=day.date,
                )
            )
    return violations


def _validate_r04(plan: WeeklyPlan) -> list[ValidationViolation]:
    """R04: Consolidation Day = fatigue ≤ 2 only."""
    violations: list[ValidationViolation] = []
    for day in plan.days:
        if not _has_block_type(day.cards, BlockType.CONSOLIDATION_DAY):
            continue
        for card in day.cards:
            if card.block_type != BlockType.CONSOLIDATION_DAY and card.fatigue > 2:
                violations.append(
                    ValidationViolation(
                        rule_id="R04",
                        message=f"Consolidation Day has block with fatigue {card.fatigue} (>{2})",
                        day=day.date,
                    )
                )
                break
    return violations


def _validate_r05(plan: WeeklyPlan) -> list[ValidationViolation]:
    """R05: Full Mock isolation — max 1/day, no other heavy/ultra, no back-to-back."""
    violations: list[ValidationViolation] = []
    days_sorted = sorted(plan.days, key=lambda d: d.date)
    mock_dates: list = []

    for day in days_sorted:
        mock_cards = [c for c in day.cards if c.block_type == BlockType.FULL_MOCK]
        if not mock_cards:
            continue

        if len(mock_cards) > 1:
            violations.append(
                ValidationViolation(
                    rule_id="R05",
                    message="Multiple Full Mocks on same day",
                    day=day.date,
                )
            )

        # No other heavy/ultra blocks
        for card in day.cards:
            if card.block_type != BlockType.FULL_MOCK and card.fatigue >= 3:
                violations.append(
                    ValidationViolation(
                        rule_id="R05",
                        message=f"Heavy block {card.block_type.value} on Full Mock day",
                        day=day.date,
                    )
                )
                break

        # No back-to-back mock days
        if mock_dates and (day.date - mock_dates[-1]).days == 1:
            violations.append(
                ValidationViolation(
                    rule_id="R05",
                    message="Back-to-back Full Mock days",
                    day=day.date,
                )
            )
        mock_dates.append(day.date)

    return violations


def _validate_r08(plan: WeeklyPlan, profile: UserProfile, phase: Phase) -> list[ValidationViolation]:
    """R08: Daily fatigue ≤ cap."""
    violations: list[ValidationViolation] = []
    cap = compute_daily_fatigue_cap(profile.available_hours_per_day, phase)
    for day in plan.days:
        total = day.total_fatigue
        if total > cap:
            violations.append(
                ValidationViolation(
                    rule_id="R08",
                    message=f"Daily fatigue {total} exceeds cap {cap}",
                    day=day.date,
                )
            )
    return violations


def _validate_r09(plan: WeeklyPlan) -> list[ValidationViolation]:
    """R09: Core Learning max 2 subjects/day, Core Retention max 4."""
    violations: list[ValidationViolation] = []
    for day in plan.days:
        cl_subjects = {
            c.subject for c in day.cards
            if c.category == BlockCategory.CORE_LEARNING and c.subject is not None
        }
        cr_subjects = {
            c.subject for c in day.cards
            if c.category == BlockCategory.CORE_RETENTION and c.subject is not None
        }
        if len(cl_subjects) > 2:
            violations.append(
                ValidationViolation(
                    rule_id="R09",
                    message=f"Core Learning has {len(cl_subjects)} subjects (max 2)",
                    day=day.date,
                )
            )
        if len(cr_subjects) > 4:
            violations.append(
                ValidationViolation(
                    rule_id="R09",
                    message=f"Core Retention has {len(cr_subjects)} subjects (max 4)",
                    day=day.date,
                )
            )
    return violations


def _validate_r12(plan: WeeklyPlan, profile: UserProfile) -> list[ValidationViolation]:
    """R12: ≤3 hrs/day → max 1 heavy block."""
    violations: list[ValidationViolation] = []
    if profile.available_hours_per_day > 3:
        return violations
    for day in plan.days:
        heavy_count = sum(1 for c in day.cards if c.fatigue >= 3)
        if heavy_count > 1:
            violations.append(
                ValidationViolation(
                    rule_id="R12",
                    message=f"{heavy_count} heavy blocks for ≤3hr user (max 1)",
                    day=day.date,
                )
            )
    return violations


def _validate_r13(plan: WeeklyPlan) -> list[ValidationViolation]:
    """R13: Max 4 consecutive heavy days, then light-only required."""
    violations: list[ValidationViolation] = []
    days_sorted = sorted(plan.days, key=lambda d: d.date)
    consecutive_heavy = 0

    for day in days_sorted:
        has_heavy = any(c.fatigue >= 3 for c in day.cards)
        if has_heavy:
            consecutive_heavy += 1
            if consecutive_heavy > 4:
                violations.append(
                    ValidationViolation(
                        rule_id="R13",
                        message=f"Day {consecutive_heavy} consecutive heavy (max 4)",
                        day=day.date,
                    )
                )
        else:
            consecutive_heavy = 0

    return violations


def validate_weekly_plan(
    plan: WeeklyPlan, profile: UserProfile, phase: Phase
) -> ValidationResult:
    """Run all hard rule validators on a weekly plan."""
    violations: list[ValidationViolation] = []
    violations.extend(_validate_r03(plan))
    violations.extend(_validate_r04(plan))
    violations.extend(_validate_r05(plan))
    violations.extend(_validate_r08(plan, profile, phase))
    violations.extend(_validate_r09(plan))
    violations.extend(_validate_r12(plan, profile))
    violations.extend(_validate_r13(plan))
    return ValidationResult(valid=len(violations) == 0, violations=violations)
