from datetime import date

import pytest

from preptrack.engine.priority import (
    compute_prelims_priority,
    compute_recency_penalty,
    rank_subjects,
)
from preptrack.models.enums import Subject


class TestRecencyPenalty:
    def test_zero_days(self):
        assert compute_recency_penalty(0) == 1.0

    def test_seven_days(self):
        assert compute_recency_penalty(7) == 2.0

    def test_fourteen_days(self):
        assert compute_recency_penalty(14) == 3.0

    def test_capped_at_21(self):
        assert compute_recency_penalty(21) == 4.0
        assert compute_recency_penalty(100) == 4.0

    def test_none_gives_max(self):
        assert compute_recency_penalty(None) == 4.0

    def test_three_days(self):
        assert abs(compute_recency_penalty(3) - 1.4285714285714286) < 1e-9


class TestPrelimsPriority:
    def test_low_confidence_high_weight(self):
        # conf=1.0, weight=0.203 (History), practiced today
        p = compute_prelims_priority(1.0, 0.203, 0)
        assert abs(p - (1.0 - 0.2) * 0.203 * 1.0) < 1e-9

    def test_high_confidence_gets_floor(self):
        # conf=5.0 → (1 - 1.0) * w * r = 0, floored at 0.01 * w
        p = compute_prelims_priority(5.0, 0.203, 0)
        assert abs(p - 0.01 * 0.203) < 1e-9

    def test_recency_boosts_priority(self):
        p_recent = compute_prelims_priority(2.0, 0.172, 0)
        p_stale = compute_prelims_priority(2.0, 0.172, 14)
        assert p_stale > p_recent

    def test_none_days_gives_max_recency(self):
        p = compute_prelims_priority(3.0, 0.189, None)
        expected = (1.0 - 3.0 / 5.0) * 0.189 * 4.0
        assert abs(p - expected) < 1e-9


class TestRankSubjects:
    def test_fresh_user_ranks_by_weight(self, fresh_confidences, subject_weights):
        """All conf=1.0, no practice → rank by weight (all have same recency)."""
        today = date(2026, 2, 25)
        ranked = rank_subjects(fresh_confidences, subject_weights, today)
        assert len(ranked) == 6
        # All same confidence and recency, so order should be by weight
        assert ranked[0].subject == Subject.HISTORY
        assert ranked[-1].subject == Subject.SCI_TECH

    def test_varied_user_respects_confidence_and_recency(self, varied_confidences, subject_weights):
        today = date(2026, 2, 25)
        ranked = rank_subjects(varied_confidences, subject_weights, today)
        # SCI_TECH: low conf (1.2), 20 days stale → should rank high
        # POLITY: high conf (4.0), practiced today → should rank low
        subjects = [r.subject for r in ranked]
        assert subjects.index(Subject.SCI_TECH) < subjects.index(Subject.POLITY)

    def test_only_prelims_subjects_ranked(self, varied_confidences, subject_weights):
        today = date(2026, 2, 25)
        ranked = rank_subjects(varied_confidences, subject_weights, today)
        ranked_subjects = {r.subject for r in ranked}
        # ETHICS, ESSAY, OPTIONAL, CSAT have no prelims weight → excluded
        assert Subject.ETHICS not in ranked_subjects
