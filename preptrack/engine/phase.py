from datetime import date

from preptrack.models.enums import Phase
from preptrack.models.kb import PhaseBlueprint


def determine_phase(
    prelims_date: date | None,
    mains_date: date | None,
    prelims_cleared: bool,
    today: date,
) -> Phase:
    """Determine current study phase based on dates and status."""
    if prelims_cleared:
        return Phase.MAINS_SPRINT_90

    if prelims_date is None:
        return Phase.FOUNDATION

    days_to_prelims = (prelims_date - today).days

    if days_to_prelims <= 75:
        return Phase.PRELIMS_SPRINT_75
    if days_to_prelims <= 240:
        return Phase.CONSOLIDATION
    return Phase.FOUNDATION


def compute_blend_percentages(
    current_phase: Phase,
    previous_phase: Phase | None,
    days_in_phase: int,
    blueprints: dict[Phase, PhaseBlueprint],
) -> dict[str, float]:
    """Compute blended category percentages for phase transitions.

    Returns dict of BlockCategory name → percentage.
    70/30 blend for first 15 days when blend is enabled.
    """
    current_bp = blueprints[current_phase]
    current_allocs = {a.category.value: a.percentage for a in current_bp.allocations}

    if (
        not current_bp.blend_enabled
        or previous_phase is None
        or days_in_phase > 15
        or previous_phase not in blueprints
    ):
        return current_allocs

    prev_bp = blueprints[previous_phase]
    prev_allocs = {a.category.value: a.percentage for a in prev_bp.allocations}

    blended: dict[str, float] = {}
    all_categories = set(current_allocs) | set(prev_allocs)
    for cat in all_categories:
        cur = current_allocs.get(cat, 0.0)
        prev = prev_allocs.get(cat, 0.0)
        blended[cat] = 0.7 * cur + 0.3 * prev

    return blended
