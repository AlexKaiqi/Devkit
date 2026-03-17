"""Unit tests for methodology ontology loading and querying."""

import sys
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.models import ChangeType, Phase, GateType, GateCheckDef
from methodology.ontology import _Ontology, get_ontology


_SAMPLE_METHODOLOGY = """
classes:
  ChangeType:
    instances: [new_capability, bug_fix, refactoring, doc_revision]
  Phase:
    instances: [classify, requirements, design, implementation, verification, finalize]
  GateType:
    instances: [hard_block, soft_warn, skip_with_reason]

mandatory_paths:
  new_capability:
    phases:
      - classify
      - requirements
      - design
      - implementation
      - verification
      - finalize
    gates:
      requirements->design:
        - type: hard_block
          check: acceptance_case_exists
          message: "新能力必须先有验收场景"
      design->implementation:
        - type: hard_block
          check: design_decision_exists
          message: "新能力必须先有设计决策"

  bug_fix:
    phases:
      - classify
      - implementation
      - verification
      - finalize
    gates:
      verification->finalize:
        - type: soft_warn
          check: regression_case_created
          message: "建议沉淀回归用例"

  doc_revision:
    phases:
      - classify
      - implementation
      - finalize
    gates: {}
"""

_SAMPLE_GATE_CHECKS = """
gate_checks:
  acceptance_case_exists:
    type: deterministic
    fs_check: "requirements/acceptance/**/*{feature_slug}*.json"
    description: "扫描 requirements/acceptance/ 目录"

  design_decision_exists:
    type: deterministic
    fs_check:
      - "design/decisions/*{feature_slug}*.md"
      - "design/architecture/*{feature_slug}*.md"
    description: "扫描 design/decisions/ 或 design/architecture/"

  regression_case_created:
    type: deterministic
    fs_check: "requirements/acceptance/regressions/*{feature_slug}*.json"
    description: "扫描 regressions 目录"

  existing_tests_pass:
    type: runtime
    command: ".venv/bin/pytest implementation/tests/unit/ -q --tb=no"
    pass_condition: "exit_code == 0"
    description: "运行单元测试"
"""


def _make_ontology(methodology_yaml=_SAMPLE_METHODOLOGY, gate_checks_yaml=_SAMPLE_GATE_CHECKS):
    """Create an ontology instance with patched file loading."""
    import yaml
    ontology = _Ontology()
    ontology._methodology = yaml.safe_load(methodology_yaml)
    ontology._gate_checks = yaml.safe_load(gate_checks_yaml)
    ontology._parse_paths()
    ontology._loaded = True
    return ontology


class TestOntologyLoading:
    def test_parses_new_capability_phases(self):
        ontology = _make_ontology()
        path = ontology.get_mandatory_path(ChangeType.new_capability)
        assert path is not None
        assert Phase.classify in path.phases
        assert Phase.requirements in path.phases
        assert Phase.design in path.phases
        assert Phase.implementation in path.phases

    def test_parses_bug_fix_phases(self):
        ontology = _make_ontology()
        path = ontology.get_mandatory_path(ChangeType.bug_fix)
        assert path is not None
        # bug_fix doesn't have requirements phase
        assert Phase.requirements not in path.phases
        assert Phase.implementation in path.phases

    def test_parses_doc_revision_empty_gates(self):
        ontology = _make_ontology()
        path = ontology.get_mandatory_path(ChangeType.doc_revision)
        assert path is not None
        assert path.gates == {}

    def test_returns_none_for_unknown_change_type(self):
        ontology = _make_ontology()
        # behavior_change not in our sample YAML
        result = ontology.get_mandatory_path(ChangeType.behavior_change)
        assert result is None


class TestGetGates:
    def test_gets_hard_block_gate(self):
        ontology = _make_ontology()
        gates = ontology.get_gates(
            ChangeType.new_capability,
            Phase.requirements,
            Phase.design,
        )
        assert len(gates) == 1
        gate = gates[0]
        assert gate.check_key == "acceptance_case_exists"
        assert gate.gate_type == GateType.hard_block
        assert "验收场景" in gate.message

    def test_gets_second_gate(self):
        ontology = _make_ontology()
        gates = ontology.get_gates(
            ChangeType.new_capability,
            Phase.design,
            Phase.implementation,
        )
        assert len(gates) == 1
        assert gates[0].check_key == "design_decision_exists"

    def test_returns_empty_for_no_gate(self):
        ontology = _make_ontology()
        # No gate from classify to requirements
        gates = ontology.get_gates(
            ChangeType.new_capability,
            Phase.classify,
            Phase.requirements,
        )
        assert gates == []

    def test_returns_empty_for_unknown_change_type(self):
        ontology = _make_ontology()
        gates = ontology.get_gates(
            ChangeType.behavior_change,
            Phase.requirements,
            Phase.design,
        )
        assert gates == []

    def test_soft_warn_gate(self):
        ontology = _make_ontology()
        gates = ontology.get_gates(
            ChangeType.bug_fix,
            Phase.verification,
            Phase.finalize,
        )
        assert len(gates) == 1
        assert gates[0].gate_type == GateType.soft_warn


class TestGetNextPhase:
    def test_next_phase_from_classify(self):
        ontology = _make_ontology()
        next_p = ontology.get_next_phase(ChangeType.new_capability, Phase.classify)
        assert next_p == Phase.requirements

    def test_next_phase_from_requirements(self):
        ontology = _make_ontology()
        next_p = ontology.get_next_phase(ChangeType.new_capability, Phase.requirements)
        assert next_p == Phase.design

    def test_returns_none_for_last_phase(self):
        ontology = _make_ontology()
        next_p = ontology.get_next_phase(ChangeType.new_capability, Phase.finalize)
        assert next_p is None

    def test_returns_none_for_unknown_change_type(self):
        ontology = _make_ontology()
        next_p = ontology.get_next_phase(ChangeType.behavior_change, Phase.classify)
        assert next_p is None

    def test_bug_fix_path(self):
        ontology = _make_ontology()
        # bug_fix: classify -> implementation
        next_p = ontology.get_next_phase(ChangeType.bug_fix, Phase.classify)
        assert next_p == Phase.implementation


class TestIsPhaseRequired:
    def test_required_phase(self):
        ontology = _make_ontology()
        assert ontology.is_phase_required(ChangeType.new_capability, Phase.requirements) is True
        assert ontology.is_phase_required(ChangeType.new_capability, Phase.design) is True

    def test_not_required_phase(self):
        ontology = _make_ontology()
        # bug_fix doesn't have requirements phase
        assert ontology.is_phase_required(ChangeType.bug_fix, Phase.requirements) is False

    def test_unknown_change_type(self):
        ontology = _make_ontology()
        assert ontology.is_phase_required(ChangeType.behavior_change, Phase.classify) is False


class TestGetGateCheckDef:
    def test_returns_definition(self):
        ontology = _make_ontology()
        check_def = ontology.get_gate_check_def("acceptance_case_exists")
        assert check_def is not None
        assert check_def["type"] == "deterministic"
        assert "fs_check" in check_def

    def test_returns_none_for_unknown(self):
        ontology = _make_ontology()
        check_def = ontology.get_gate_check_def("nonexistent_check")
        assert check_def is None

    def test_runtime_check(self):
        ontology = _make_ontology()
        check_def = ontology.get_gate_check_def("existing_tests_pass")
        assert check_def is not None
        assert check_def["type"] == "runtime"
        assert "command" in check_def
        assert "pass_condition" in check_def


class TestListChangeTypes:
    def test_lists_change_types(self):
        ontology = _make_ontology()
        change_types = ontology.list_change_types()
        assert ChangeType.new_capability in change_types
        assert ChangeType.bug_fix in change_types
        assert ChangeType.doc_revision in change_types
        # behavior_change not in sample
        assert ChangeType.behavior_change not in change_types


class TestRealOntologyFiles:
    """Integration test: load the real methodology.yaml and gate-checks.yaml files."""

    def test_real_files_load(self):
        """Test that the actual YAML files can be loaded."""
        ontology = get_ontology()
        # Should load successfully
        change_types = ontology.list_change_types()
        assert len(change_types) > 0

    def test_real_new_capability_path(self):
        """Test new_capability path from real files."""
        ontology = get_ontology()
        path = ontology.get_mandatory_path(ChangeType.new_capability)
        assert path is not None
        assert Phase.requirements in path.phases
        assert Phase.design in path.phases
        assert Phase.implementation in path.phases

    def test_real_gates_exist(self):
        """Test that gates are defined in real files."""
        ontology = get_ontology()
        gates = ontology.get_gates(
            ChangeType.new_capability,
            Phase.requirements,
            Phase.design,
        )
        assert len(gates) > 0
        gate = gates[0]
        assert gate.gate_type == GateType.hard_block
