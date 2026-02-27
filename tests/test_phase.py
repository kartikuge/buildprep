from datetime import date

import pytest

from preptrack.engine.phase import compute_blend_percentages, determine_phase
from preptrack.models.enums import Phase


class TestDeterminePhase:
    def test_no_prelims_date(self):
        assert determine_phase(None, None, False, date(2026, 3, 1)) == Phase.FOUNDATION

    def test_far_from_prelims(self):
        # 300 days out → FOUNDATION
        assert determine_phase(date(2027, 1, 1), None, False, date(2026, 3, 1)) == Phase.FOUNDATION

    def test_consolidation(self):
        # 200 days out → CONSOLIDATION
        assert determine_phase(date(2026, 9, 15), None, False, date(2026, 3, 1)) == Phase.CONSOLIDATION

    def test_exactly_240(self):
        # 240 days → CONSOLIDATION (≤240)
        prelims = date(2026, 10, 27)
        today = date(2026, 3, 1)
        assert (prelims - today).days == 240
        assert determine_phase(prelims, None, False, today) == Phase.CONSOLIDATION

    def test_prelims_sprint(self):
        # 60 days out → PRELIMS_SPRINT_75
        assert determine_phase(date(2026, 5, 1), None, False, date(2026, 3, 2)) == Phase.PRELIMS_SPRINT_75

    def test_exactly_75(self):
        prelims = date(2026, 5, 15)
        today = date(2026, 3, 1)
        assert (prelims - today).days == 75
        assert determine_phase(prelims, None, False, today) == Phase.PRELIMS_SPRINT_75

    def test_prelims_cleared(self):
        assert determine_phase(date(2026, 5, 25), date(2026, 9, 19), True, date(2026, 6, 1)) == Phase.MAINS_SPRINT_90

    def test_prelims_cleared_overrides_date(self):
        # Even if days_to_prelims looks like foundation, cleared → mains
        assert determine_phase(date(2027, 5, 25), None, True, date(2026, 3, 1)) == Phase.MAINS_SPRINT_90


class TestBlendPercentages:
    def test_no_blend_foundation(self, phase_blueprints):
        result = compute_blend_percentages(Phase.FOUNDATION, None, 5, phase_blueprints)
        assert result["CORE_LEARNING"] == 50.0

    def test_blend_enabled_within_window(self, phase_blueprints):
        result = compute_blend_percentages(
            Phase.PRELIMS_SPRINT_75, Phase.CONSOLIDATION, 5, phase_blueprints
        )
        # CORE_LEARNING: 0.7*5 + 0.3*30 = 3.5 + 9.0 = 12.5
        assert abs(result["CORE_LEARNING"] - 12.5) < 1e-9

    def test_blend_expired(self, phase_blueprints):
        result = compute_blend_percentages(
            Phase.PRELIMS_SPRINT_75, Phase.CONSOLIDATION, 20, phase_blueprints
        )
        assert result["CORE_LEARNING"] == 5.0  # Pure new phase

    def test_blend_at_day_15(self, phase_blueprints):
        result = compute_blend_percentages(
            Phase.CONSOLIDATION, Phase.FOUNDATION, 15, phase_blueprints
        )
        # Still within window (≤15)
        expected_cl = 0.7 * 30 + 0.3 * 50  # 21 + 15 = 36
        assert abs(result["CORE_LEARNING"] - expected_cl) < 1e-9

    def test_no_previous_phase(self, phase_blueprints):
        result = compute_blend_percentages(Phase.CONSOLIDATION, None, 5, phase_blueprints)
        assert result["CORE_LEARNING"] == 30.0
