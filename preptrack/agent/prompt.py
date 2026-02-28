"""Prompt construction for plan generation agent."""

from __future__ import annotations

from datetime import date, timedelta

from preptrack.models.enums import BlockCategory, Phase, Subject
from preptrack.models.plan import SubjectPriority, ValidationViolation
from preptrack.models.user import UserProfile


def build_system_prompt() -> str:
    """Static system prompt: role, constraints, output format."""
    return """You are PrepTrack, an expert UPSC study planner. Your job is to generate a detailed weekly study plan as structured JSON.

## Role
You produce a WeeklyPlan for a UPSC aspirant. You decide which block types, subjects, topics, and durations to assign each day. Your output must strictly follow the JSON schema described in the user prompt.

## Core Constraints
- Every PlanCard must use a valid BlockType and its matching BlockCategory and fatigue value from the block definitions.
- Card durations must fall within the block's [min_duration, max_duration] range.
- Total planned minutes per day must not exceed the user's available minutes.
- Respect all hard rules (R03, R04, R05, R08, R09, R12, R13). If you violate them, the plan will be rejected.
- Each day must have cards ordered sequentially starting from 0.
- Assign meaningful UPSC subtopics to each card (not generic labels).
- Include a brief narrative explaining your weekly strategy.

## CRITICAL — R13 Burnout Prevention (most commonly violated rule)
A "heavy day" is any day that has at least one card with fatigue >= 3.
You MUST NOT have more than 4 consecutive heavy days. After 4 heavy days in a row, the next day MUST be light-only (all cards fatigue <= 2).
Strategy: make day 5 or day 7 (Sunday) a light day using only REVISION, QUICK_RECALL, PYQ_ANALYSIS, NEWS_READING, CA_INTEGRATION, NOTE_REFINEMENT, WEEKLY_REVIEW, STUDY_LIGHT, CSAT_PRACTICE, WEAK_AREA_DRILL, or CONSOLIDATION_DAY.
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
- available_minutes_per_day: {available_minutes}""")

    # Phase
    sections.append(f"""## Current Phase
{phase.value}""")

    # Category budgets
    budget_lines = [f"- {cat.value}: {mins} minutes" for cat, mins in category_budgets.items()]
    sections.append("## Weekly Category Budgets (minutes per day)\n" + "\n".join(budget_lines))

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
    sections.append("""## Output JSON Schema

```
{
  "user_id": "<string>",
  "week_start": "<YYYY-MM-DD, Monday>",
  "days": [
    {
      "date": "<YYYY-MM-DD>",
      "cards": [
        {
          "block_type": "<BlockType enum value, e.g. DEEP_STUDY>",
          "category": "<BlockCategory enum value, e.g. CORE_LEARNING>",
          "subject": "<Subject enum value or null>",
          "topic": "<specific UPSC subtopic string>",
          "planned_duration": <int, minutes within block min/max>,
          "fatigue": <int, must match block definition>,
          "order": <int, 0-indexed sequential>
        }
      ]
    }
  ],
  "narrative": "<brief strategy explanation>"
}
```

Valid BlockType values: DEEP_STUDY, STUDY_LIGHT, STUDY_TECHNICAL, REVISION, QUICK_RECALL, PYQ_ANALYSIS, TIMED_MCQ, TIMED_ANSWER_WRITING, CSAT_PRACTICE, ESSAY_BRAINSTORM, ESSAY_FULL_SIM, FULL_MOCK, INTERVIEW_SIM, ERROR_ANALYSIS, WEAK_AREA_DRILL, CONSOLIDATION_DAY, NEWS_READING, CA_INTEGRATION, NOTE_REFINEMENT, WEEKLY_REVIEW

Valid Subject values: HISTORY, ECONOMY, POLITY, ENVIRONMENT, GEOGRAPHY, SCI_TECH, ETHICS, ESSAY, OPTIONAL, CSAT

Valid BlockCategory values: CORE_LEARNING, CORE_RETENTION, CORE_PATTERN, PERFORMANCE, CORRECTIVE, RETENTION, INPUT, PROCESSING, META

Do NOT include card_id, actual_duration, or status fields — they are auto-generated.""")

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
        print(f"DEBUG: Including {len(violations)} violations in prompt:\n" + "\n".join(violation_lines))

    return "\n\n".join(sections)
