"""Plan generation agent: LLM proposes, engine validates."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

from strands import Agent
from strands.models import BedrockModel

from preptrack.agent.exceptions import PlanGenerationError
from preptrack.agent.prompt import build_plan_prompt, build_system_prompt
from preptrack.engine.allocator import allocate_minutes
from preptrack.engine.phase import compute_blend_percentages, determine_phase
from preptrack.engine.priority import rank_subjects
from preptrack.engine.validator import validate_weekly_plan
from preptrack.kb import BLOCK_DEFINITIONS, PHASE_BLUEPRINTS, SUBJECT_WEIGHTS, load_kb_markdown
from preptrack.models.enums import BlockCategory, BlockType, Phase
from preptrack.models.plan import DailyPlan, PlanCard, SubjectPriority, ValidationViolation, WeeklyPlan
from preptrack.models.user import TopicConfidence, UserProfile

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

KB_DIR = "knowledgebase"


def _next_monday(from_date: date) -> date:
    """Return the next Monday on or after from_date."""
    days_ahead = (7 - from_date.weekday()) % 7
    if days_ahead == 0 and from_date.weekday() != 0:
        days_ahead = 7
    return from_date + timedelta(days=days_ahead)


def _compute_context(
    profile: UserProfile,
    confidences: list[TopicConfidence],
    previous_phase: Phase | None,
    days_in_phase: int,
    today: date,
) -> tuple[Phase, dict[BlockCategory, int], list[SubjectPriority]]:
    """Compute deterministic context: phase, budgets, priorities."""
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

    return phase, category_budgets, subject_priorities


def _extract_json(text: str) -> str | None:
    """Extract JSON object from LLM text response, handling markdown fences."""
    # Try to find JSON in code fences first
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # Try to find a raw JSON object
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return None


def _call_llm(agent: Agent, user_prompt: str) -> WeeklyPlan | None:
    """Call LLM and parse the raw JSON response into WeeklyPlan.

    Makes a single Bedrock call. The system prompt instructs Nova to return
    pure JSON, which we extract and validate with Pydantic.

    Note: Strands structured_output (tool-use based) does not work reliably
    with Nova 2 Lite — it consistently returns None. We skip it entirely
    to avoid a wasted API call.
    """
    try:
        result = agent(user_prompt)
        raw_text = str(result)
        logger.debug("Raw LLM response (first 2000 chars):\n%.2000s", raw_text)
        json_str = _extract_json(raw_text)
        if json_str:
            data = json.loads(json_str)
            plan = WeeklyPlan.model_validate(data)
            logger.info(
                "LLM response parsed — %d days, %d cards",
                len(plan.days),
                sum(len(d.cards) for d in plan.days),
            )
            return plan
        logger.warning("No JSON object found in LLM response")
    except Exception as e:
        logger.warning("LLM call failed: %s", e)

    return None


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


def _repair_r13(plan: WeeklyPlan) -> WeeklyPlan:
    """Deterministically fix R13 violations by downgrading heavy cards on day 5+.

    After 4 consecutive heavy days, subsequent days must be light-only
    until a naturally light day resets the counter.
    """
    days_sorted = sorted(plan.days, key=lambda d: d.date)
    consecutive_heavy = 0
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

        # Day 5+ of consecutive heavy — downgrade all heavy cards
        new_cards = []
        for card in day.cards:
            if card.fatigue >= 3:
                replacement_type = _LIGHT_REPLACEMENTS.get(card.block_type, BlockType.REVISION)
                replacement_def = _BLOCK_DEF[replacement_type]
                duration = max(replacement_def.min_duration, min(card.planned_duration, replacement_def.max_duration))
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
        consecutive_heavy = 0  # Reset after repair (now a light day)

    if repaired:
        logger.info("R13 repair: downgraded heavy blocks on consecutive day 5+")

    return plan


def generate_plan(
    profile: UserProfile,
    confidences: list[TopicConfidence],
    week_start: date | None = None,
    previous_phase: Phase | None = None,
    days_in_phase: int = 30,
    model_id: str = "us.amazon.nova-2-lite-v1:0",
    region: str = "us-east-1",
) -> WeeklyPlan:
    """Generate a validated weekly study plan.

    1. Compute deterministic context (phase, budgets, priorities)
    2. Build prompt with KB context
    3. Call Nova 2 Lite via Strands structured_output
    4. Validate with engine
    5. Retry up to MAX_RETRIES on validation failure
    6. Return validated WeeklyPlan

    Raises PlanGenerationError if all retries exhausted.
    """
    today = date.today()
    if week_start is None:
        week_start = _next_monday(today)

    # 1. Deterministic pre-computation
    phase, category_budgets, subject_priorities = _compute_context(
        profile, confidences, previous_phase, days_in_phase, today
    )
    logger.info("Phase: %s | Budgets: %s", phase.value, {k.value: v for k, v in category_budgets.items()})
    logger.info("Subject priorities: %s", [(p.subject.value, round(p.raw_priority, 3)) for p in subject_priorities])

    # Load KB markdown for prompt context
    kb_context = load_kb_markdown(KB_DIR)
    logger.info("Loaded %d KB sections: %s", len(kb_context), list(kb_context.keys()))

    # 2. Initialize Strands agent
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

    # 3. Retry loop
    violations: list[ValidationViolation] | None = None
    last_violations: list[ValidationViolation] = []

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("Plan generation attempt %d/%d", attempt, MAX_RETRIES)

        # Build prompt (includes violations on retry)
        user_prompt = build_plan_prompt(
            profile=profile,
            phase=phase,
            category_budgets=category_budgets,
            subject_priorities=subject_priorities,
            kb_context=kb_context,
            week_start=week_start,
            violations=violations,
        )

        # Call LLM
        plan = _call_llm(agent, user_prompt)

        if plan is None:
            logger.warning("Attempt %d/%d: LLM returned unparseable output", attempt, MAX_RETRIES)
            violations = [
                ValidationViolation(
                    rule_id="PARSE",
                    message="Failed to parse LLM output into WeeklyPlan. "
                    "Return ONLY valid JSON matching the schema exactly.",
                )
            ]
            last_violations = violations
            continue

        # 3.5 Deterministic repair for common LLM mistakes
        plan = _repair_r13(plan)

        # 4. Validate
        validation = validate_weekly_plan(plan, profile, phase)
        if validation.valid:
            logger.info(
                "Plan validated on attempt %d — %d days, %d total cards",
                attempt,
                len(plan.days),
                sum(len(d.cards) for d in plan.days),
            )
            return plan

        # Validation failed — prepare for retry
        violations = validation.violations
        last_violations = validation.violations
        logger.warning(
            "Attempt %d failed with %d violations: %s",
            attempt,
            len(violations),
            [v.message for v in violations],
        )

    # All retries exhausted
    raise PlanGenerationError(
        f"Plan generation failed after {MAX_RETRIES} attempts. "
        f"Last violations: {[v.message for v in last_violations]}",
        violations=last_violations,
    )
