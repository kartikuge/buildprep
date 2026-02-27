import math

from preptrack.models.enums import Phase
from preptrack.models.plan import DailyPlan


def compute_daily_fatigue_cap(hours: float, phase: Phase) -> int:
    """Compute daily fatigue cap based on hours and phase. Floor decimals."""
    low_hours = hours <= 2.0
    if phase in (Phase.MAINS_SPRINT_90, Phase.INTERVIEW):
        mult = 3.0 if low_hours else 2.5
    else:
        mult = 2.5 if low_hours else 2.0
    return math.floor(hours * mult)


def compute_daily_fatigue(cards: list) -> int:
    """Sum fatigue values of all cards."""
    return sum(c.fatigue for c in cards)


def check_fatigue_cap(daily_plan: DailyPlan, cap: int) -> bool:
    """Return True if daily plan is within fatigue cap."""
    return daily_plan.total_fatigue <= cap
