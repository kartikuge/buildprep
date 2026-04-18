"""Prompt construction for plan generation and rebalancing agents."""

from __future__ import annotations

from datetime import date, timedelta

from preptrack.engine.fatigue import compute_daily_fatigue_cap
from preptrack.models.enums import BlockCategory, Phase, Subject
from preptrack.models.plan import DailyPlan, SubjectPriority, ValidationViolation
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
    plan_dates: list[date] | None = None,
    violations: list[ValidationViolation] | None = None,
    missed_context: dict[str, int] | None = None,
) -> str:
    """User prompt with all context the LLM needs to generate a WeeklyPlan."""
    available_minutes = int(profile.available_hours_per_day * 60)
    min_daily = int(available_minutes * 0.85)
    fatigue_cap = compute_daily_fatigue_cap(profile.available_hours_per_day, phase)
    if plan_dates is None:
        plan_dates = [week_start + timedelta(days=i) for i in range(7)]
    week_dates = [d.isoformat() for d in plan_dates]

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
    num_days = len(week_dates)
    sections.append(f"""## Week to Plan
- week_start: {week_start.isoformat()} (Monday, storage key)
- dates to generate: {', '.join(week_dates)}
- Generate exactly {num_days} DailyPlan object{'s' if num_days > 1 else ''}, one per date listed above.
- Apply R13 (burnout prevention) across these {num_days} days as if they are a full planning window.""")

    # Priority recovery context (from cross-week rebalance)
    if missed_context:
        missed_lines = [
            f"- {subj}: ~{mins}m missed" for subj, mins in sorted(missed_context.items(), key=lambda x: -x[1])
        ]
        sections.append(
            "## Priority Recovery (from previous week)\n"
            "The user fell behind on these subjects last week. Prioritize them in your plan, "
            "but generate a NORMAL schedule that respects all constraints. Do NOT overstuff.\n"
            + "\n".join(missed_lines)
        )

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


def build_rebalance_prompt(
    profile: UserProfile,
    phase: Phase,
    category_budgets: dict[BlockCategory, int],
    subject_priorities: list[SubjectPriority],
    kb_context: dict[str, str],
    recovery_dates: list[date],
    missed_content: list[dict],
    consecutive_heavy_before: int,
    frozen_ca_count: int,
    frozen_days: list[DailyPlan],
    violations: list[ValidationViolation] | None = None,
) -> str:
    """Build prompt for rebalancing: regenerate only recovery days with missed content context."""
    available_minutes = int(profile.available_hours_per_day * 60)
    min_daily = int(available_minutes * 0.85)
    fatigue_cap = compute_daily_fatigue_cap(profile.available_hours_per_day, phase)

    sections: list[str] = []

    # Context: this is a rebalance, not a fresh plan
    sections.append(f"""## Task: REBALANCE (not fresh generation)
You are regenerating ONLY specific recovery days for a user who missed some study days.
The user's completed days are FROZEN and cannot change. You must generate cards ONLY for the recovery dates listed below.

CRITICAL CONSTRAINT: Each recovery day's total fatigue MUST be ≤ {fatigue_cap}. This is a HARD ceiling — the plan is REJECTED if any day exceeds it.
- Do NOT try to cram all missed content into recovery days.
- Treat each recovery day as a NORMAL study day with normal budgets.
- Weave in missed SUBJECTS (not necessarily the same blocks/durations) where they naturally fit.
- If missed content doesn't fit within the fatigue cap, DROP IT. A valid plan is more important than covering everything.""")

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
    sections.append(f"## Current Phase\n{phase.value}")

    # Category budgets
    budget_total = sum(category_budgets.values())
    budget_lines = [f"- {cat.value}: {mins} minutes/day" for cat, mins in category_budgets.items()]
    sections.append(
        f"## Daily Category Budgets\n"
        f"These are PER-DAY targets. Each recovery day should have approximately {available_minutes} total minutes.\n"
        f"Budget breakdown per day (total {budget_total}m + ~20m news = {budget_total + 20}m):\n"
        + "\n".join(budget_lines)
        + f"\n\nYou MUST fill at least {min_daily} minutes per day."
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

    # Recovery dates — ONLY these days to generate
    date_strs = [d.isoformat() for d in recovery_dates]
    sections.append(f"""## Recovery Dates to Generate
Generate exactly {len(recovery_dates)} DailyPlan objects for these dates ONLY:
- {', '.join(date_strs)}""")

    # Missed content — what the user skipped
    if missed_content:
        # Summarize by subject instead of listing every card — less temptation to overstuff
        subject_summary: dict[str, int] = {}
        for mc in missed_content:
            subj = mc.get("subject") or "General"
            subject_summary[subj] = subject_summary.get(subj, 0) + mc.get("planned_duration", 0)
        missed_lines = [f"- {subj}: ~{mins}m missed" for subj, mins in sorted(subject_summary.items(), key=lambda x: -x[1])]
        sections.append(
            "## Missed Subjects (for context — DO NOT try to fit all of this)\n"
            "The user missed study time in these subjects. Use this to BIAS your subject selection "
            "toward these areas, but generate a NORMAL schedule that respects all constraints.\n"
            "Do NOT add extra blocks or inflate durations to compensate. Just prefer these subjects "
            "when choosing what to study on recovery days.\n"
            + "\n".join(missed_lines)
        )
    else:
        sections.append(
            "## Missed Content\n"
            "No specific missed content to redistribute. Generate a normal schedule for the recovery days."
        )

    # Fatigue carryover — R13 context
    remaining_heavy = max(0, 4 - consecutive_heavy_before)
    sections.append(f"""## Fatigue Carryover (R13 — Burnout Prevention)
The {consecutive_heavy_before} day(s) immediately before the recovery window were heavy (fatigue >= 3).
This means:
- You can schedule at most {remaining_heavy} consecutive heavy day(s) at the START of the recovery window before a light day is required.
- If {consecutive_heavy_before} >= 4, the FIRST recovery day MUST be light-only (all fatigue <= 2).
- After any light day, the counter resets and you get 4 more heavy days.""")

    # R21 context — CA_INTEGRATION already used
    if frozen_ca_count > 0:
        sections.append(f"""## R21 — CA Integration Already Scheduled
There are already {frozen_ca_count} CA_INTEGRATION block(s) in the frozen (completed) days this week.
Since the max is 1 per week, do NOT schedule any CA_INTEGRATION in the recovery days.""")
    else:
        sections.append("## R21 — CA Integration\nNo CA_INTEGRATION in frozen days. You may schedule at most 1 in the recovery days.")

    # Frozen days summary — so LLM knows what was already done
    if frozen_days:
        frozen_summary_lines = []
        for day in sorted(frozen_days, key=lambda d: d.date):
            subjects_done = set()
            total_min = 0
            for card in day.cards:
                if card.subject:
                    subjects_done.add(card.subject.value)
                total_min += card.planned_duration
            heavy = "heavy" if any(c.fatigue >= 3 for c in day.cards) else "light"
            frozen_summary_lines.append(
                f"- {day.date.isoformat()} ({heavy}): {total_min}m — subjects: {', '.join(sorted(subjects_done)) or 'none'}"
            )
        sections.append(
            "## Frozen Days (already completed, for context only)\n"
            + "\n".join(frozen_summary_lines)
        )

    # KB context
    for section_name, content in sorted(kb_context.items()):
        sections.append(f"## Knowledge Base: {section_name}\n{content}")

    # Output schema — same as plan but only recovery days
    sections.append(f"""## Output JSON Schema

```
{{
  "days": [
    {{
      "date": "<YYYY-MM-DD, must be one of the recovery dates>",
      "cards": [
        {{
          "block_type": "<BlockType enum value>",
          "category": "<BlockCategory enum value>",
          "subject": "<Subject enum value or null>",
          "topic": "<specific UPSC subtopic string>",
          "planned_duration": <int, minutes within block min/max>,
          "fatigue": <int, MUST match block definition for duration>,
          "order": <int, 0-indexed sequential>
        }}
      ]
    }}
  ],
  "narrative": "<1-2 sentence summary of what changed: which missed subjects were incorporated and how the recovery days differ from a normal schedule>"
}}
```

Valid BlockType values: DEEP_STUDY, STUDY_LIGHT, STUDY_TECHNICAL, REVISION, QUICK_RECALL, PYQ_ANALYSIS, TIMED_MCQ, TIMED_ANSWER_WRITING, CSAT_PRACTICE, ESSAY_BRAINSTORM, ESSAY_FULL_SIM, FULL_MOCK, INTERVIEW_SIM, ERROR_ANALYSIS, WEAK_AREA_DRILL, CONSOLIDATION_DAY, NEWS_READING, CA_INTEGRATION, NOTE_REFINEMENT, WEEKLY_REVIEW

Valid Subject values: HISTORY, ECONOMY, POLITY, ENVIRONMENT, GEOGRAPHY, SCI_TECH, ETHICS, ESSAY, OPTIONAL, CSAT

Valid BlockCategory values: CORE_LEARNING, CORE_RETENTION, CORE_PATTERN, PERFORMANCE, CORRECTIVE, RETENTION, INPUT, PROCESSING, META

Duration-based fatigue reminder:
- DEEP_STUDY: ≤90 min → fatigue 2, >90 min → fatigue 3
- STUDY_TECHNICAL: ≤90 min → fatigue 2, >90 min → fatigue 3
- TIMED_ANSWER_WRITING: ≤60 min → fatigue 2, >60 min → fatigue 3

Do NOT include card_id, actual_duration, or status fields.

REMEMBER: Each recovery day MUST have at least {min_daily} total planned minutes. Target {available_minutes} minutes per day.
Generate ONLY the recovery dates: {', '.join(date_strs)}""")

    # Violations from previous attempt
    if violations:
        violation_lines = []
        for v in violations:
            day_str = f" on {v.day.isoformat()}" if v.day else ""
            violation_lines.append(f"- [{v.rule_id}]{day_str}: {v.message}")
        sections.append(
            "## PREVIOUS ATTEMPT REJECTED — Fix These Violations\n"
            "Your previous rebalance was rejected. Fix ALL violations:\n"
            + "\n".join(violation_lines)
        )

    return "\n\n".join(sections)
