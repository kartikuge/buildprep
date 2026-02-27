import pytest

from preptrack.engine.fatigue import check_fatigue_cap, compute_daily_fatigue, compute_daily_fatigue_cap
from preptrack.models.enums import Phase


class TestFatigueCap:
    def test_foundation_standard(self):
        assert compute_daily_fatigue_cap(6.0, Phase.FOUNDATION) == 12

    def test_foundation_low_hours(self):
        assert compute_daily_fatigue_cap(2.0, Phase.FOUNDATION) == 5

    def test_mains_sprint_standard(self):
        assert compute_daily_fatigue_cap(5.0, Phase.MAINS_SPRINT_90) == 12

    def test_mains_sprint_low_hours(self):
        assert compute_daily_fatigue_cap(2.0, Phase.MAINS_SPRINT_90) == 6

    def test_interview_standard(self):
        assert compute_daily_fatigue_cap(4.0, Phase.INTERVIEW) == 10

    def test_working_pro_prelims(self):
        # 2.5 hrs, not low-hours (>2), standard mult
        assert compute_daily_fatigue_cap(2.5, Phase.PRELIMS_SPRINT_75) == 5

    def test_floor_decimals(self):
        assert compute_daily_fatigue_cap(3.5, Phase.FOUNDATION) == 7  # 3.5 * 2 = 7.0


class TestDailyFatigue:
    def test_empty(self):
        assert compute_daily_fatigue([]) == 0

    def test_sum(self):
        class FakeCard:
            def __init__(self, f):
                self.fatigue = f
        cards = [FakeCard(3), FakeCard(1), FakeCard(2)]
        assert compute_daily_fatigue(cards) == 6


class TestCheckFatigueCap:
    def test_within_cap(self):
        from datetime import date
        from tests.conftest import make_card, make_daily
        day = make_daily(date(2026, 3, 2), [make_card(fatigue=2), make_card(fatigue=3)])
        assert check_fatigue_cap(day, 10) is True

    def test_exceeds_cap(self):
        from datetime import date
        from tests.conftest import make_card, make_daily
        day = make_daily(date(2026, 3, 2), [make_card(fatigue=3), make_card(fatigue=3), make_card(fatigue=3)])
        assert check_fatigue_cap(day, 8) is False
