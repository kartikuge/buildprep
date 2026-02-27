import pytest

from preptrack.engine.allocator import allocate_minutes
from preptrack.models.enums import BlockCategory


class TestAllocateMinutes:
    def test_foundation_6hrs(self):
        percentages = {
            "CORE_LEARNING": 50, "CORE_RETENTION": 17, "CORE_PATTERN": 8,
            "PERFORMANCE": 5, "CORRECTIVE": 5, "INPUT": 5, "PROCESSING": 5, "META": 5,
        }
        result = allocate_minutes(360, percentages, news_minutes=20)
        # 360 - 20 = 340 remaining
        assert sum(result.values()) == 340
        assert result[BlockCategory.CORE_LEARNING] >= 168  # ~50% of 340

    def test_news_deducted_first(self):
        percentages = {"CORE_LEARNING": 100}
        result = allocate_minutes(100, percentages, news_minutes=20)
        assert result[BlockCategory.CORE_LEARNING] == 80

    def test_zero_remaining(self):
        percentages = {"CORE_LEARNING": 50, "CORE_RETENTION": 50}
        result = allocate_minutes(20, percentages, news_minutes=20)
        assert sum(result.values()) == 0

    def test_rounding_sums_correctly(self):
        percentages = {
            "CORE_LEARNING": 33, "CORE_RETENTION": 33, "CORE_PATTERN": 34,
        }
        result = allocate_minutes(200, percentages, news_minutes=20)
        assert sum(result.values()) == 180  # 200 - 20

    def test_low_hours_user(self):
        percentages = {
            "CORE_LEARNING": 50, "CORE_RETENTION": 25, "CORE_PATTERN": 25,
        }
        result = allocate_minutes(150, percentages, news_minutes=20)
        # 130 remaining
        assert sum(result.values()) == 130
