"""Tests for preptrack.kb — static config constants and KB markdown loader."""

from pathlib import Path

from preptrack.kb import (
    BLOCK_DEFINITIONS,
    CONFIDENCE_CONFIG,
    PHASE_BLUEPRINTS,
    RULES,
    SUBJECT_WEIGHTS,
    load_kb_markdown,
)
from preptrack.models.enums import BlockType, Phase


KB_DIR = str(Path(__file__).parent.parent / "knowledgebase")


class TestBlockDefinitions:
    def test_has_20_blocks(self):
        assert len(BLOCK_DEFINITIONS) == 20

    def test_all_block_types_covered(self):
        defined_types = {b.block_type for b in BLOCK_DEFINITIONS}
        expected_types = set(BlockType)
        assert defined_types == expected_types

    def test_no_duplicate_block_types(self):
        types = [b.block_type for b in BLOCK_DEFINITIONS]
        assert len(types) == len(set(types))


class TestPhaseBlueprints:
    def test_has_5_phases(self):
        assert len(PHASE_BLUEPRINTS) == 5

    def test_all_phases_present(self):
        assert set(PHASE_BLUEPRINTS.keys()) == set(Phase)

    def test_allocations_sum_to_100(self):
        for phase, bp in PHASE_BLUEPRINTS.items():
            total = sum(a.percentage for a in bp.allocations)
            assert total == 100, f"{phase} allocations sum to {total}, expected 100"


class TestSubjectWeights:
    def test_has_10_subjects(self):
        assert len(SUBJECT_WEIGHTS) == 10

    def test_prelims_weights_sum_to_1(self):
        prelims = [sw.prelims_weight for sw in SUBJECT_WEIGHTS if sw.prelims_weight is not None]
        assert len(prelims) == 6
        total = sum(prelims)
        assert abs(total - 1.0) < 0.01, f"Prelims weights sum to {total}"


class TestConfidenceConfig:
    def test_streak_milestones_count(self):
        assert len(CONFIDENCE_CONFIG.streak_milestones) == 3

    def test_session_milestones_count(self):
        assert len(CONFIDENCE_CONFIG.session_milestones) == 3

    def test_skip_penalties_count(self):
        assert len(CONFIDENCE_CONFIG.skip_penalties) == 3

    def test_confidence_bounds(self):
        assert CONFIDENCE_CONFIG.min_confidence == 1.0
        assert CONFIDENCE_CONFIG.max_confidence == 5.0


class TestRules:
    def test_has_19_rules(self):
        # R01-R17, R19, R20 (no R18)
        assert len(RULES) == 19

    def test_all_rule_types_valid(self):
        valid_types = {"hard", "medium", "low", "deferred"}
        for rule in RULES:
            assert rule.rule_type in valid_types, f"{rule.rule_id} has invalid type '{rule.rule_type}'"

    def test_unique_rule_ids(self):
        ids = [r.rule_id for r in RULES]
        assert len(ids) == len(set(ids))

    def test_all_rules_have_descriptions(self):
        for rule in RULES:
            assert len(rule.description) > 0, f"{rule.rule_id} has empty description"


class TestLoadKbMarkdown:
    def test_loads_all_6_files(self):
        result = load_kb_markdown(KB_DIR)
        assert len(result) == 6

    def test_expected_keys(self):
        result = load_kb_markdown(KB_DIR)
        expected = {
            "block_definitions",
            "confidence_model",
            "engine_reference",
            "phase_blueprints",
            "rules",
            "subject_weights",
        }
        assert set(result.keys()) == expected

    def test_all_values_non_empty(self):
        result = load_kb_markdown(KB_DIR)
        for key, content in result.items():
            assert len(content) > 0, f"{key} loaded as empty string"
