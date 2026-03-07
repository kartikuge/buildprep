"""Prompt construction for plan generation agent."""

from __future__ import annotations

from datetime import date, timedelta

from preptrack.engine.fatigue import compute_daily_fatigue_cap
from preptrack.models.enums import BlockCategory, Phase, Subject
from preptrack.models.plan import SubjectPriority, ValidationViolation
from preptrack.models.user import UserProfile


def build_system_prompt() -> str:
    """Static system prompt: role, constraints, output format."""
    return """You are PrepTrack, an expert UPSC study planner. Your job is to generate a detailed weekly study plan as structured JSON.

## Role
You produce a WeeklyPlan for a UPSC aspirant. You decide which block types, subjects, topics, and durations to assign each day. Your output must strictly follow the JSON schema described in the user prompt.

## Core Constraints
- Every PlanCard must use a valid BlockType and its matching BlockCategory from the block definitions.
- Card durations must fall within the block's [min_duration, max_duration] range.
- Fatigue MUST match the block definition for the chosen duration. Some blocks have duration-based fatigue (see below).
- You MUST schedule at least 85% of available daily minutes. If the fatigue cap is not reached, keep adding low-fatigue blocks (REVISION, QUICK_RECALL, PYQ_ANALYSIS, STUDY_LIGHT, WEAK_AREA_DRILL, NOTE_REFINEMENT). Do NOT under-schedule.
- The category budgets are PER DAY targets, not weekly totals.
- Respect all hard rules (R03, R04, R05, R08, R09, R12, R13, R21). If you violate them, the plan will be rejected.
- Each day must have cards ordered sequentially starting from 0.
- Assign meaningful UPSC subtopics to each card (not generic labels).
- Include a brief narrative explaining your weekly strategy.

## Duration-Based Fatigue
Three blocks have fatigue that depends on their duration. This is a key lever for fitting more study time:
- DEEP_STUDY: 45-90 min → fatigue 2 (not heavy), 91-120 min → fatigue 3 (heavy)
- STUDY_TECHNICAL: 60-90 min → fatigue 2 (not heavy), 91-120 min → fatigue 3 (heavy)
- TIMED_ANSWER_WRITING: 45-60 min → fatigue 2 (not heavy), 61-90 min → fatigue 3 (heavy)

Use shorter durations (fatigue 2) when you need to fit more blocks under the fatigue cap. Use longer durations (fatigue 3) when fatigue budget allows deeper sessions.

## R09 — Topic Diversity (Hard)
- Core Learning: Max 2 distinct subjects/day. Min 2 if 2+ blocks scheduled. If available_hours ≥ 8, max 3 distinct subjects/day. Depth over breadth — when Core Learning budget exceeds 120 min/day, prefer longer block durations (90-120 min) over adding more subjects. A 90-min Deep Study is more valuable than two 45-min sessions on different topics.
- Core Retention: Max 4 distinct subjects/day. If available_hours ≥ 8, max 5 distinct subjects/day. Same principle: prefer deeper revision on fewer subjects over shallow passes on many.
- Other categories: Topic-agnostic, no diversity constraint.

## CRITICAL — R13 Burnout Prevention (most commonly violated rule)
A "heavy day" is any day that has at least one card with fatigue >= 3.
You MUST NOT have more than 4 consecutive heavy days. After 4 heavy days in a row, the next day MUST be light-only (all cards fatigue <= 2).
Strategy: make day 5 or day 7 (Sunday) a light day using only REVISION, QUICK_RECALL, PYQ_ANALYSIS, NEWS_READING, NOTE_REFINEMENT, WEEKLY_REVIEW, STUDY_LIGHT, CSAT_PRACTICE, WEAK_AREA_DRILL, or CONSOLIDATION_DAY. You can also use DEEP_STUDY/STUDY_TECHNICAL at short durations (fatigue 2) on light days.
Example valid pattern: Heavy, Heavy, Heavy, Heavy, Light, Heavy, Heavy.
Example INVALID pattern: Heavy, Heavy, Heavy, Heavy, Heavy, Heavy, Light - REJECTED.

## Output Format
Respond with ONLY valid JSON matching the WeeklyPlan schema. No markdown, no explanation, no code fences - just the JSON object."""


def build_plan_prompt(
    profile: UserProfile,
    phase: Phase,
    category_budgets: dict[BlockCategory, int],
    subject_priorities: list[SubjectPriority],
    kb_context: dict[str, str],
    week_start: date,
    violations: list[ValidationViolation] | None = None,
) -> str:
    """User prompt with all context the LLM needs to generate a WeeklyPlan."""
    available_minutes = int(profile.available_hours_per_day * 60)
    min_daily = int(available_minutes * 0.85)
    fatigue_cap = compute_daily_fatigue_cap(profile.available_hours_per_day, phase)
    week_dates = [(week_start + timedelta(days=i)).isoformat() for i in range(7)]

    sections: list[str] = []

    # User profile
    sections.append(f"""## User Profile
- user_id: {profile.user_id}
- stage: {profile.stage}
- optional_subject: {profile.optional_subject or "None"}
- prelims_date: {profile.prelims_date or "Not set"}
- mains_date: {profile.mains_date or "Not set"}
- available_hours_per_day: {profile.available_hours_per_day}
- available_minutes_per_day: {available_minutes}
- MINIMUM minutes per day: {min_daily} (85% of {available_minutes})
- DAILY FATIGUE CAP: {fatigue_cap} (pre-computed, do NOT recalculate)""")

    # Phase
    sections.append(f"""## Current Phase
{phase.value}""")

    # Category budgets
    budget_total = sum(category_budgets.values())
    budget_lines = [f"- {cat.value}: {mins} minutes/day" for cat, mins in category_budgets.items()]
    sections.append(
        f"## Daily Category Budgets\n"
        f"IMPORTANT: These are PER-DAY targets. Each day should have approximately {available_minutes} total minutes of study ({profile.available_hours_per_day} hours).\n"
        f"Budget breakdown per day (total {budget_total}m + ~20m news = {budget_total + 20}m):\n"
        + "\n".join(budget_lines)
        + f"\n\nYou MUST fill at least {min_daily} minutes per day. If fatigue cap is not reached, add more low-fatigue blocks."
    )

    # Subject priorities
    if subject_priorities:
        priority_lines = []
        for sp in subject_priorities:
            priority_lines.append(
                f"- {sp.subject.value}: priority={sp.raw_priority:.3f}, "
                f"confidence={sp.normalized_confidence:.2f}, "
                f"weight={sp.weight:.3f}, "
                f"recency_penalty={sp.recency_penalty:.2f}"
            )
        sections.append("## Subject Priorities (ranked by need)\n" + "\n".join(priority_lines))

    # Week dates
    sections.append(f"""## Week to Plan
- week_start: {week_start.isoformat()} (Monday)
- dates: {', '.join(week_dates)}
- Generate exactly 7 DailyPlan objects, one per date.""")

    # KB context
    for section_name, content in sorted(kb_context.items()):
        sections.append(f"## Knowledge Base: {section_name}\n{content}")

    # Output schema
    sections.append(f"""## Output JSON Schema

```
{{
  "user_id": "<string>",
  "week_start": "<YYYY-MM-DD, Monday>",
  "days": [
    {{
      "date": "<YYYY-MM-DD>",
      "cards": [
        {{
          "block_type": "<BlockType enum value, e.g. DEEP_STUDY>",
          "category": "<BlockCategory enum value, e.g. CORE_LEARNING>",
          "subject": "<Subject enum value or null>",
          "topic": "<specific UPSC subtopic string>",
          "planned_duration": <int, minutes within block min/max>,
          "fatigue": <int, MUST match block definition for duration — see duration-based fatigue rules>,
          "order": <int, 0-indexed sequential>
        }}
      ]
    }}
  ],
  "narrative": "<brief strategy explanation>"
}}
```

Valid BlockType values: DEEP_STUDY, STUDY_LIGHT, STUDY_TECHNICAL, REVISION, QUICK_RECALL, PYQ_ANALYSIS, TIMED_MCQ, TIMED_ANSWER_WRITING, CSAT_PRACTICE, ESSAY_BRAINSTORM, ESSAY_FULL_SIM, FULL_MOCK, INTERVIEW_SIM, ERROR_ANALYSIS, WEAK_AREA_DRILL, CONSOLIDATION_DAY, NEWS_READING, CA_INTEGRATION, NOTE_REFINEMENT, WEEKLY_REVIEW

Valid Subject values: HISTORY, ECONOMY, POLITY, ENVIRONMENT, GEOGRAPHY, SCI_TECH, ETHICS, ESSAY, OPTIONAL, CSAT

Valid BlockCategory values: CORE_LEARNING, CORE_RETENTION, CORE_PATTERN, PERFORMANCE, CORRECTIVE, RETENTION, INPUT, PROCESSING, META

Duration-based fatigue reminder:
- DEEP_STUDY: ≤90 min → fatigue 2, >90 min → fatigue 3
- STUDY_TECHNICAL: ≤90 min → fatigue 2, >90 min → fatigue 3
- TIMED_ANSWER_WRITING: ≤60 min → fatigue 2, >60 min → fatigue 3

Do NOT include card_id, actual_duration, or status fields — they are auto-generated.

REMEMBER: Each day MUST have at least {min_daily} total planned minutes. Target {available_minutes} minutes per day.""")

    # Violations from previous attempt
    if violations:
        violation_lines = []
        for v in violations:
            day_str = f" on {v.day.isoformat()}" if v.day else ""
            violation_lines.append(f"- [{v.rule_id}]{day_str}: {v.message}")
        sections.append(
            "## PREVIOUS ATTEMPT REJECTED — Fix These Violations\n"
            "Your previous plan was rejected by the validation engine. "
            "You MUST fix ALL of the following violations:\n"
            + "\n".join(violation_lines)
        )

    return "\n\n".join(sections)
