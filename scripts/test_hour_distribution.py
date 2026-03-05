"""Test plan generation across 4 user profiles with different daily hours.

Usage:
    python scripts/test_hour_distribution.py

Requires AWS credentials and DynamoDB Local is NOT needed (storage not used).
"""

import logging
import sys
from datetime import date
from preptrack.models.user import UserProfile, TopicConfidence
from preptrack.models.enums import Subject, Phase
from preptrack.engine.fatigue import compute_daily_fatigue_cap
from preptrack.engine.phase import determine_phase
from preptrack.agent.planner import generate_plan, _compute_context

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

TODAY = date(2026, 2, 28)
WEEK_START = date(2026, 3, 2)

USERS = [
    # UserProfile(
    #     user_id="test-4h",
    #     display_name="4-Hour User",
    #     optional_subject="Sociology",
    #     stage="both",
    #     prelims_date=date(2026, 5, 25),
    #     mains_date=date(2026, 9, 19),
    #     available_hours_per_day=4.0,
    # ),
    # UserProfile(
    #     user_id="test-6h",
    #     display_name="6-Hour User",
    #     optional_subject="PSIR",
    #     stage="both",
    #     prelims_date=date(2026, 5, 25),
    #     mains_date=date(2026, 9, 19),
    #     available_hours_per_day=6.0,
    # ),
    # UserProfile(
    #     user_id="test-8h",
    #     display_name="8-Hour User",
    #     optional_subject="Sociology",
    #     stage="both",
    #     prelims_date=date(2026, 5, 25),
    #     mains_date=date(2026, 9, 19),
    #     available_hours_per_day=8.0,
    # ),
    UserProfile(
        user_id="test-10h",
        display_name="10-Hour User",
        optional_subject="Geography",
        stage="both",
        prelims_date=date(2026, 5, 25),
        mains_date=date(2026, 9, 19),
        available_hours_per_day=10.0,
    ),
]

CONFIDENCES_MAP = {
    "test-4h": [
        TopicConfidence(user_id="test-4h", subject=Subject.HISTORY, perceived_confidence=2.0),
        TopicConfidence(user_id="test-4h", subject=Subject.ECONOMY, perceived_confidence=1.5),
        TopicConfidence(user_id="test-4h", subject=Subject.POLITY, perceived_confidence=3.0),
        TopicConfidence(user_id="test-4h", subject=Subject.ENVIRONMENT, perceived_confidence=2.5),
        TopicConfidence(user_id="test-4h", subject=Subject.GEOGRAPHY, perceived_confidence=1.0),
        TopicConfidence(user_id="test-4h", subject=Subject.SCI_TECH, perceived_confidence=2.0),
    ],
    "test-6h": [
        TopicConfidence(user_id="test-6h", subject=Subject.HISTORY, perceived_confidence=3.5),
        TopicConfidence(user_id="test-6h", subject=Subject.ECONOMY, perceived_confidence=2.0),
        TopicConfidence(user_id="test-6h", subject=Subject.POLITY, perceived_confidence=4.0),
        TopicConfidence(user_id="test-6h", subject=Subject.ENVIRONMENT, perceived_confidence=1.5),
        TopicConfidence(user_id="test-6h", subject=Subject.GEOGRAPHY, perceived_confidence=2.8),
        TopicConfidence(user_id="test-6h", subject=Subject.SCI_TECH, perceived_confidence=1.2),
    ],
    "test-8h": [
        TopicConfidence(user_id="test-8h", subject=Subject.HISTORY, perceived_confidence=2.5),
        TopicConfidence(user_id="test-8h", subject=Subject.ECONOMY, perceived_confidence=3.0),
        TopicConfidence(user_id="test-8h", subject=Subject.POLITY, perceived_confidence=2.0),
        TopicConfidence(user_id="test-8h", subject=Subject.ENVIRONMENT, perceived_confidence=1.0),
        TopicConfidence(user_id="test-8h", subject=Subject.GEOGRAPHY, perceived_confidence=3.5),
        TopicConfidence(user_id="test-8h", subject=Subject.SCI_TECH, perceived_confidence=2.0),
    ],
    "test-10h": [
        TopicConfidence(user_id="test-10h", subject=Subject.HISTORY, perceived_confidence=1.5),
        TopicConfidence(user_id="test-10h", subject=Subject.ECONOMY, perceived_confidence=2.0),
        TopicConfidence(user_id="test-10h", subject=Subject.POLITY, perceived_confidence=3.0),
        TopicConfidence(user_id="test-10h", subject=Subject.ENVIRONMENT, perceived_confidence=2.0),
        TopicConfidence(user_id="test-10h", subject=Subject.GEOGRAPHY, perceived_confidence=1.0),
        TopicConfidence(user_id="test-10h", subject=Subject.SCI_TECH, perceived_confidence=4.0),
    ],
}


def print_deterministic_context():
    """Print what the engine computes for each user (no LLM needed)."""
    print("\n" + "=" * 80)
    print("DETERMINISTIC CONTEXT (no LLM call)")
    print("=" * 80)

    for user in USERS:
        confs = CONFIDENCES_MAP[user.user_id]
        phase, budgets, priorities = _compute_context(user, confs, None, 30, TODAY)
        fatigue_cap = compute_daily_fatigue_cap(user.available_hours_per_day, phase)
        daily_mins = int(user.available_hours_per_day * 60)
        budget_total = sum(budgets.values())

        print(f"\n--- {user.display_name} ({user.available_hours_per_day}h/day) ---")
        print(f"  Phase: {phase.value}")
        print(f"  Daily minutes: {daily_mins}")
        print(f"  Fatigue cap: {fatigue_cap}")
        print(f"  Category budgets (daily, sum={budget_total}m):")
        for cat, mins in sorted(budgets.items(), key=lambda x: -x[1]):
            print(f"    {cat.value:20s}: {mins:4d} min")
        print(f"  Top priorities:")
        for p in priorities[:4]:
            print(f"    {p.subject.value:12s}: priority={p.raw_priority:.3f}")


def run_generation(user: UserProfile):
    """Run actual plan generation and print hour analysis."""
    confs = CONFIDENCES_MAP[user.user_id]

    print(f"\n{'='*60}")
    print(f"GENERATING PLAN: {user.display_name} ({user.available_hours_per_day}h/day)")
    print(f"{'='*60}")

    try:
        plan = generate_plan(
            profile=user,
            confidences=confs,
            week_start=WEEK_START,
        )

        daily_target = int(user.available_hours_per_day * 60)
        phase = determine_phase(user.prelims_date, user.mains_date, user.prelims_cleared, TODAY)
        fatigue_cap = compute_daily_fatigue_cap(user.available_hours_per_day, phase)
        total_week_mins = 0

        print(f"\n  Target: {daily_target}m/day | Fatigue cap: {fatigue_cap}")
        print(f"  {'Day':<12} {'Mins':>6} {'Fatigue':>8} {'Cards':>6} {'Util%':>6}")
        print(f"  {'-'*42}")

        for day in sorted(plan.days, key=lambda d: d.date):
            mins = sum(c.planned_duration for c in day.cards)
            fat = sum(c.fatigue for c in day.cards)
            util = (mins / daily_target * 100) if daily_target > 0 else 0
            total_week_mins += mins
            print(f"  {day.date.isoformat():<12} {mins:>5}m {fat:>7} {len(day.cards):>6} {util:>5.0f}%")

        avg_daily = total_week_mins / 7
        weekly_target = daily_target * 7
        print(f"  {'-'*42}")
        print(f"  Weekly total: {total_week_mins}m / {weekly_target}m target ({total_week_mins/weekly_target*100:.0f}%)")
        print(f"  Avg daily: {avg_daily:.0f}m ({avg_daily/60:.1f}h) vs target {daily_target}m ({user.available_hours_per_day}h)")
        print(f"\n  Narrative: {plan.narrative[:]}...")

    except Exception as e:
        print(f"  FAILED: {e}")


if __name__ == "__main__":
    # Always print deterministic context
    print_deterministic_context()

    # If --generate flag, run actual LLM calls
    if "--generate" in sys.argv:
        for user in USERS:
            run_generation(user)
    else:
        print("\n\nTo run actual LLM generation, add --generate flag:")
        print("  python scripts/test_hour_distribution.py --generate")
