"""Rebalancing agent: redistribute missed study content into recovery days."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, date, datetime, timedelta

from strands import Agent
from strands.models import BedrockModel

from preptrack.agent.exceptions import PlanGenerationError
from preptrack.agent.prompt import build_rebalance_prompt, build_system_prompt
from preptrack.engine.allocator import allocate_minutes
from preptrack.engine.fatigue import compute_daily_fatigue_cap
from preptrack.engine.phase import compute_blend_percentages, determine_phase
from preptrack.engine.priority import rank_subjects
from preptrack.engine.validator import validate_weekly_plan
from preptrack.kb import BLOCK_DEFINITIONS, PHASE_BLUEPRINTS, SUBJECT_WEIGHTS, load_kb_markdown
from preptrack.models.enums import BlockCategory, BlockType, CheckInStatus, Phase
from preptrack.models.plan import DailyPlan, PlanCard, SubjectPriority, ValidationViolation, WeeklyPlan
from preptrack.models.user import RecoveryState, TopicConfidence, UserProfile

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
KB_DIR = "knowledgebase"

# Lookup: block_type → BlockDefinition for duration limits
_BLOCK_DEF = {bd.block_type: bd for bd in BLOCK_DEFINITIONS}

# Light block types to substitute when repairing R13
_LIGHT_REPLACEMENTS = {
    BlockType.DEEP_STUDY: BlockType.REVISION,
    BlockType.STUDY_TECHNICAL: BlockType.REVISION,
    BlockType.TIMED_MCQ: BlockType.PYQ_ANALYSIS,
    BlockType.TIMED_ANSWER_WRITING: BlockType.PYQ_ANALYSIS,
    BlockType.ERROR_ANALYSIS: BlockType.WEAK_AREA_DRILL,
    BlockType.FULL_MOCK: BlockType.REVISION,
    BlockType.ESSAY_FULL_SIM: BlockType.ESSAY_BRAINSTORM,
    BlockType.INTERVIEW_SIM: BlockType.REVISION,
}


def classify_days(
    plan: WeeklyPlan,
    today: date,
) -> tuple[list[DailyPlan], list[DailyPlan], list[DailyPlan]]:
    """Classify each day in the plan as frozen, missed, or recovery-eligible.

    Returns (frozen_days, missed_days, eligible_recovery_days).

    - Frozen: at least 1 card is DONE or PARTIAL (user engaged).
    - Missed: no engagement AND (day is past OR day is finalized with all skips).
    - Recovery-eligible: unfrozen, non-finalized days from today onward.
    """
    frozen = []
    missed = []
    eligible = []

    for day in sorted(plan.days, key=lambda d: d.date):
        statuses = {c.status for c in day.cards}
        has_engagement = CheckInStatus.DONE in statuses or CheckInStatus.PARTIAL in statuses

        if has_engagement:
            frozen.append(day)
        elif day.date < today or day.finalized:
            # Past day with no engagement, OR finalized with all skips = missed
            missed.append(day)
        else:
            # Today or future, not finalized, no engagement = eligible for recovery
            eligible.append(day)

    return frozen, missed, eligible


def extract_missed_content(missed_days: list[DailyPlan]) -> list[dict]:
    """Extract content from missed days for redistribution.

    Returns list of dicts with subject, topic, block_type, category, duration.
    """
    content = []
    for day in missed_days:
        for card in day.cards:
            content.append({
                "subject": card.subject.value if card.subject else None,
                "topic": card.topic,
                "block_type": card.block_type.value,
                "category": card.category.value,
                "planned_duration": card.planned_duration,
                "date": day.date.isoformat(),
            })
    return content


def compute_fatigue_carryover(frozen_days: list[DailyPlan], recovery_start: date) -> int:
    """Count consecutive heavy days immediately before the recovery window.

    For R13: if frozen days end with N consecutive heavy days, the recovery
    window starts with that count, so the LLM knows how many more heavy days
    it can schedule before needing a light day.
    """
    # Sort frozen days by date, look backwards from recovery start
    relevant = sorted(
        [d for d in frozen_days if d.date < recovery_start],
        key=lambda d: d.date,
        reverse=True,
    )
    consecutive = 0
    for day in relevant:
        has_heavy = any(c.fatigue >= 3 for c in day.cards)
        if has_heavy:
            consecutive += 1
        else:
            break
    return consecutive


def extract_missed_context(missed_days: list[DailyPlan]) -> dict[str, int]:
    """Extract subject-level missed minutes from missed days.

    Returns dict of Subject value → total missed minutes.
    Used by cross-week rebalance to pass priority context to next-week generation.
    """
    subject_minutes: dict[str, int] = {}
    for day in missed_days:
        for card in day.cards:
            if card.subject:
                key = card.subject.value
                subject_minutes[key] = subject_minutes.get(key, 0) + card.planned_duration
    return subject_minutes


def count_frozen_ca_integrations(frozen_days: list[DailyPlan]) -> int:
    """Count CA_INTEGRATION blocks in frozen days for R21 enforcement."""
    return sum(
        1
        for day in frozen_days
        for card in day.cards
        if card.block_type == BlockType.CA_INTEGRATION
    )


def _extract_json(text: str) -> str | None:
    """Extract JSON object from LLM text response."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return None


def _correct_fatigue_days(days: list[DailyPlan]) -> list[DailyPlan]:
    """Overwrite LLM-assigned fatigue with correct values."""
    for day in days:
        for card in day.cards:
            defn = _BLOCK_DEF.get(card.block_type)
            if defn is None:
                continue
            correct = defn.fatigue_for_duration(card.planned_duration)
            if card.fatigue != correct:
                logger.debug(
                    "Fatigue correction: %s %dm — %d → %d",
                    card.block_type.value,
                    card.planned_duration,
                    card.fatigue,
                    correct,
                )
                card.fatigue = correct
    return days


def _repair_r13_with_context(
    plan: WeeklyPlan, consecutive_heavy_before: int
) -> WeeklyPlan:
    """Fix R13 violations considering fatigue carryover from frozen days."""
    days_sorted = sorted(plan.days, key=lambda d: d.date)
    consecutive_heavy = consecutive_heavy_before
    repaired = False

    for day in days_sorted:
        has_heavy = any(c.fatigue >= 3 for c in day.cards)

        if has_heavy:
            consecutive_heavy += 1
        else:
            consecutive_heavy = 0
            continue

        if consecutive_heavy <= 4:
            continue

        # Day 5+ — downgrade all heavy cards
        new_cards = []
        for card in day.cards:
            if card.fatigue >= 3:
                replacement_type = _LIGHT_REPLACEMENTS.get(card.block_type, BlockType.REVISION)
                replacement_def = _BLOCK_DEF[replacement_type]
                duration = max(
                    replacement_def.min_duration,
                    min(card.planned_duration, replacement_def.max_duration),
                )
                new_card = card.model_copy(update={
                    "block_type": replacement_type,
                    "category": replacement_def.category,
                    "fatigue": replacement_def.fatigue,
                    "planned_duration": duration,
                })
                new_cards.append(new_card)
                repaired = True
            else:
                new_cards.append(card)

        day.cards = new_cards
        consecutive_heavy = 0

    if repaired:
        logger.info("R13 repair: downgraded heavy blocks on consecutive day 5+")

    return plan


def _call_rebalance_llm(
    agent: Agent,
    user_prompt: str,
    recovery_dates: list[date],
) -> tuple[list[DailyPlan], str] | None:
    """Call LLM and parse response into recovery DailyPlans + narrative."""
    try:
        result = agent(user_prompt)

        stop_reason = getattr(result, "stop_reason", "unknown")
        metrics = getattr(result, "metrics", None)
        usage = getattr(metrics, "accumulated_usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        acc_metrics = getattr(metrics, "accumulated_metrics", {})
        latency = acc_metrics.get("latencyMs", "unknown")

        logger.info(
            "Rebalance LLM | Stop: %s | Tokens: In=%s, Out=%s | Latency: %sms",
            stop_reason, input_tokens, output_tokens, latency,
        )

        raw_text = str(result)
        logger.debug("Raw rebalance LLM response (first 2000 chars):\n%.2000s", raw_text)

        json_str = _extract_json(raw_text)
        if not json_str:
            logger.warning("No JSON object found in rebalance LLM response")
            return None

        data = json.loads(json_str)

        # Parse the days array from the response
        days_data = data.get("days", [])
        if not days_data:
            logger.warning("No 'days' in rebalance LLM response")
            return None

        narrative = data.get("narrative", "")

        recovery_days = []
        for day_data in days_data:
            daily = DailyPlan.model_validate(day_data)
            recovery_days.append(daily)

        logger.info(
            "Rebalance LLM parsed — %d recovery days, %d cards",
            len(recovery_days),
            sum(len(d.cards) for d in recovery_days),
        )
        return recovery_days, narrative

    except Exception as e:
        logger.warning("Rebalance LLM call failed: %s", e)
        return None


def rebalance_plan(
    plan: WeeklyPlan,
    profile: UserProfile,
    confidences: list[TopicConfidence],
    recovery_window_days: int,
    today: date | None = None,
    previous_phase: Phase | None = None,
    days_in_phase: int = 30,
    model_id: str = "us.amazon.nova-2-lite-v1:0",
    region: str = "us-east-1",
) -> tuple[WeeklyPlan, list[date], list[date], str]:
    """Rebalance a weekly plan by redistributing missed content into recovery days.

    Returns (updated_plan, missed_dates, recovery_dates, narrative).

    Raises PlanGenerationError if all retries exhausted.
    """
    if today is None:
        today = date.today()

    # 1. Classify days
    frozen_days, missed_days, eligible_days = classify_days(plan, today)
    logger.info(
        "Day classification — frozen: %d, missed: %d, eligible: %d",
        len(frozen_days), len(missed_days), len(eligible_days),
    )

    if not missed_days and not eligible_days:
        raise PlanGenerationError(
            "No days to rebalance: all days are frozen (DONE/PARTIAL).",
            violations=[],
        )

    if not eligible_days:
        raise PlanGenerationError(
            "No recovery days available: all remaining days are in the past.",
            violations=[],
        )

    # 2. Select recovery days (capped by recovery_window_days)
    recovery_days_target = eligible_days[:recovery_window_days]
    recovery_dates = [d.date for d in recovery_days_target]

    # Days that are eligible but outside recovery window stay as-is
    unchanged_eligible = eligible_days[recovery_window_days:]

    logger.info(
        "Missed dates: %s | Recovery dates: %s",
        [d.date.isoformat() for d in missed_days],
        [d.isoformat() for d in recovery_dates],
    )

    # 3. Extract missed content
    missed_content = extract_missed_content(missed_days)

    # 4. Compute context
    phase = determine_phase(
        prelims_date=profile.prelims_date,
        mains_date=profile.mains_date,
        prelims_cleared=profile.prelims_cleared,
        today=today,
    )

    percentages = compute_blend_percentages(
        current_phase=phase,
        previous_phase=previous_phase,
        days_in_phase=days_in_phase,
        blueprints=PHASE_BLUEPRINTS,
    )

    available_minutes = int(profile.available_hours_per_day * 60)
    category_budgets = allocate_minutes(available_minutes, percentages)
    subject_priorities = rank_subjects(confidences, SUBJECT_WEIGHTS, today)

    # 5. Compute fatigue carryover for R13
    recovery_start = recovery_dates[0] if recovery_dates else today
    consecutive_heavy_before = compute_fatigue_carryover(frozen_days, recovery_start)

    # 6. Count existing CA_INTEGRATION in frozen days for R21
    frozen_ca_count = count_frozen_ca_integrations(frozen_days)

    # 7. Load KB
    kb_context = load_kb_markdown(KB_DIR)

    # 8. Build LLM agent
    system_prompt = build_system_prompt()
    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=0.3,
        max_tokens=5120,
    )
    agent = Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        callback_handler=None,
    )

    # 9. Retry loop
    violations: list[ValidationViolation] | None = None
    last_violations: list[ValidationViolation] = []

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("Rebalance attempt %d/%d", attempt, MAX_RETRIES)

        user_prompt = build_rebalance_prompt(
            profile=profile,
            phase=phase,
            category_budgets=category_budgets,
            subject_priorities=subject_priorities,
            kb_context=kb_context,
            recovery_dates=recovery_dates,
            missed_content=missed_content,
            consecutive_heavy_before=consecutive_heavy_before,
            frozen_ca_count=frozen_ca_count,
            frozen_days=frozen_days,
            violations=violations,
        )

        result = _call_rebalance_llm(agent, user_prompt, recovery_dates)

        if result is None:
            logger.warning("Attempt %d: LLM returned unparseable output", attempt)
            violations = [
                ValidationViolation(
                    rule_id="PARSE",
                    message="Failed to parse rebalance output. Return ONLY valid JSON.",
                )
            ]
            last_violations = violations
            continue

        new_days, narrative = result

        # Correct fatigue on new days
        _correct_fatigue_days(new_days)

        # Merge: frozen + new recovery days + unchanged eligible
        merged_days = list(frozen_days) + list(missed_days) + new_days + list(unchanged_eligible)
        merged_days.sort(key=lambda d: d.date)

        # Build merged plan
        merged_plan = plan.model_copy(update={
            "days": merged_days,
            "generated_at": datetime.now(UTC),
        })

        # R13 repair with carryover context (only on recovery days portion)
        merged_plan = _repair_r13_with_context(merged_plan, 0)

        logger.info(
            "Merged plan: %d days, %d total cards",
            len(merged_plan.days),
            sum(len(d.cards) for d in merged_plan.days),
        )

        # Validate full week
        validation = validate_weekly_plan(merged_plan, profile, phase)
        if validation.valid:
            logger.info("Rebalance validated on attempt %d", attempt)
            missed_dates = [d.date for d in missed_days]
            return merged_plan, missed_dates, recovery_dates, narrative

        violations = validation.violations
        last_violations = validation.violations
        logger.warning(
            "Rebalance attempt %d failed with %d violations: %s",
            attempt,
            len(violations),
            [v.message for v in violations],
        )

    raise PlanGenerationError(
        f"Rebalance failed after {MAX_RETRIES} attempts. "
        f"Last violations: {[v.message for v in last_violations]}",
        violations=last_violations,
    )
