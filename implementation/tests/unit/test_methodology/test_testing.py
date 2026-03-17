"""Unit tests for methodology testing helper module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.testing import (
    get_testing_strategy_for_change_type,
    get_required_approaches,
    get_ordered_steps,
    get_coverage_mandate,
    list_testing_approaches,
    has_hard_block_steps,
)


class TestGetTestingStrategyForChangeType:
    def test_new_capability_strategy_exists(self):
        """new_capability strategy should be defined in testing-methodology.yaml"""
        strategy = get_testing_strategy_for_change_type("new_capability")
        assert strategy is not None
        assert "description" in strategy

    def test_bug_fix_strategy_exists(self):
        strategy = get_testing_strategy_for_change_type("bug_fix")
        assert strategy is not None

    def test_refactoring_strategy_exists(self):
        strategy = get_testing_strategy_for_change_type("refactoring")
        assert strategy is not None

    def test_unknown_change_type_returns_none(self):
        strategy = get_testing_strategy_for_change_type("unknown_type")
        assert strategy is None


class TestGetRequiredApproaches:
    def test_new_capability_required_approaches(self):
        approaches = get_required_approaches("new_capability")
        assert isinstance(approaches, list)
        assert len(approaches) > 0
        assert "unit_isolation" in approaches

    def test_refactoring_required_approaches(self):
        approaches = get_required_approaches("refactoring")
        assert "regression_guard" in approaches

    def test_doc_revision_no_required_approaches(self):
        approaches = get_required_approaches("doc_revision")
        assert approaches == []

    def test_unknown_type_returns_empty(self):
        approaches = get_required_approaches("nonexistent")
        assert approaches == []


class TestGetOrderedSteps:
    def test_new_capability_has_steps(self):
        steps = get_ordered_steps("new_capability")
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_steps_have_required_fields(self):
        steps = get_ordered_steps("new_capability")
        for step in steps:
            assert "step" in step
            assert "action" in step

    def test_bug_fix_steps(self):
        steps = get_ordered_steps("bug_fix")
        assert len(steps) > 0

    def test_unknown_type_returns_empty(self):
        steps = get_ordered_steps("nonexistent")
        assert steps == []


class TestGetCoverageMandate:
    def test_new_capability_coverage(self):
        mandate = get_coverage_mandate("new_capability")
        assert "min_percent" in mandate
        assert mandate["min_percent"] >= 0

    def test_bug_fix_no_coverage_requirement(self):
        mandate = get_coverage_mandate("bug_fix")
        assert mandate.get("min_percent", 0) == 0

    def test_unknown_type_defaults_to_zero(self):
        mandate = get_coverage_mandate("nonexistent")
        assert mandate == {"min_percent": 0}


class TestListTestingApproaches:
    def test_returns_list(self):
        approaches = list_testing_approaches()
        assert isinstance(approaches, list)

    def test_contains_known_approaches(self):
        approaches = list_testing_approaches()
        assert "unit_isolation" in approaches
        assert "regression_guard" in approaches
        assert "e2e_scenario" in approaches


class TestHasHardBlockSteps:
    def test_new_capability_has_hard_blocks(self):
        result = has_hard_block_steps("new_capability")
        assert result is True

    def test_doc_revision_no_hard_blocks(self):
        result = has_hard_block_steps("doc_revision")
        assert result is False

    def test_unknown_type_no_hard_blocks(self):
        result = has_hard_block_steps("nonexistent")
        assert result is False
