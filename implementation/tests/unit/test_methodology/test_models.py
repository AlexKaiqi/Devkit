"""Unit tests for methodology Pydantic models."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.models import (
    ChangeType,
    Phase,
    GateType,
    GateCheckDef,
    GateResult,
    MandatoryPath,
    Feature,
    InterceptResult,
)


class TestChangeType:
    def test_all_values(self):
        values = [ct.value for ct in ChangeType]
        assert "new_capability" in values
        assert "behavior_change" in values
        assert "bug_fix" in values
        assert "refactoring" in values
        assert "doc_revision" in values
        assert "eval_asset" in values
        assert len(values) == 6

    def test_from_string(self):
        ct = ChangeType("new_capability")
        assert ct == ChangeType.new_capability

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ChangeType("unknown_type")

    def test_is_string(self):
        # ChangeType extends str, can be used as string comparisons
        ct = ChangeType.new_capability
        assert ct == "new_capability"
        assert ct.value == "new_capability"


class TestPhase:
    def test_all_values(self):
        values = [p.value for p in Phase]
        # 验证原有 7 个 phase 都存在
        for v in ["classify", "requirements", "design", "implementation",
                  "verification", "asset_capture", "finalize"]:
            assert v in values, f"Phase '{v}' should exist"
        # 验证新增的 decomposition
        assert "decomposition" in values, "Phase 'decomposition' should exist"
        # 共 8 个
        assert len(values) == 8

    def test_from_string(self):
        p = Phase("implementation")
        assert p == Phase.implementation

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            Phase("unknown_phase")


class TestGateType:
    def test_all_values(self):
        values = [gt.value for gt in GateType]
        assert "hard_block" in values
        assert "soft_warn" in values
        assert "skip_with_reason" in values


class TestGateCheckDef:
    def test_valid_creation(self):
        gcd = GateCheckDef(
            name="acceptance_case_exists",
            gate_type=GateType.hard_block,
            check_key="acceptance_case_exists",
            message="新能力必须先有验收场景",
        )
        assert gcd.name == "acceptance_case_exists"
        assert gcd.gate_type == GateType.hard_block
        assert gcd.check_key == "acceptance_case_exists"

    def test_defaults(self):
        gcd = GateCheckDef(
            name="test",
            gate_type=GateType.soft_warn,
            check_key="test",
            message="",
        )
        assert gcd.message == ""


class TestGateResult:
    def test_passed(self):
        result = GateResult(
            gate_check="acceptance_case_exists",
            passed=True,
            gate_type=GateType.hard_block,
            message="新能力必须先有验收场景",
            details="找到匹配文件: requirements/acceptance/test.json",
        )
        assert result.passed is True
        assert result.skip_reason == ""

    def test_failed(self):
        result = GateResult(
            gate_check="acceptance_case_exists",
            passed=False,
            gate_type=GateType.hard_block,
            message="新能力必须先有验收场景",
        )
        assert result.passed is False
        assert result.gate_type == GateType.hard_block

    def test_with_skip_reason(self):
        result = GateResult(
            gate_check="design_decision_exists",
            passed=False,
            gate_type=GateType.skip_with_reason,
            message="需要设计决策",
            skip_reason="使用现有架构无需新决策",
        )
        assert result.skip_reason == "使用现有架构无需新决策"


class TestMandatoryPath:
    def test_basic_creation(self):
        path = MandatoryPath(
            change_type=ChangeType.new_capability,
            phases=[Phase.classify, Phase.requirements, Phase.implementation, Phase.finalize],
            gates={},
        )
        assert path.change_type == ChangeType.new_capability
        assert len(path.phases) == 4
        assert path.gates == {}

    def test_with_gates(self):
        gate = GateCheckDef(
            name="acceptance_case_exists",
            gate_type=GateType.hard_block,
            check_key="acceptance_case_exists",
            message="需要验收场景",
        )
        path = MandatoryPath(
            change_type=ChangeType.new_capability,
            phases=[Phase.requirements, Phase.design],
            gates={"requirements->design": [gate]},
        )
        assert "requirements->design" in path.gates
        assert len(path.gates["requirements->design"]) == 1

    def test_empty_gates_default(self):
        path = MandatoryPath(
            change_type=ChangeType.doc_revision,
            phases=[Phase.classify, Phase.implementation, Phase.finalize],
        )
        assert path.gates == {}


class TestFeature:
    def test_defaults(self):
        feature = Feature(
            feature_id="test-001",
            title="测试功能",
            change_type=ChangeType.new_capability,
        )
        assert feature.current_phase == Phase.classify
        assert feature.status == "active"
        assert feature.session_key == ""
        assert feature.skip_reasons == {}
        assert feature.created_at == ""

    def test_full_creation(self):
        feature = Feature(
            feature_id="feature-001",
            title="新能力",
            change_type=ChangeType.new_capability,
            current_phase=Phase.requirements,
            status="active",
            session_key="session-abc",
            skip_reasons={"design": "已有现成方案"},
            created_at="2026-03-17T10:00:00+08:00",
            updated_at="2026-03-17T10:30:00+08:00",
        )
        assert feature.current_phase == Phase.requirements
        assert feature.skip_reasons["design"] == "已有现成方案"

    def test_status_values(self):
        for status in ["active", "completed", "abandoned"]:
            feature = Feature(
                feature_id="f",
                title="t",
                change_type=ChangeType.bug_fix,
                status=status,
            )
            assert feature.status == status


class TestInterceptResult:
    def test_not_blocked(self):
        result = InterceptResult(blocked=False)
        assert result.blocked is False
        assert result.message == ""
        assert result.gate_results == []

    def test_blocked(self):
        gr = GateResult(
            gate_check="acceptance_case_exists",
            passed=False,
            gate_type=GateType.hard_block,
            message="需要验收场景",
        )
        result = InterceptResult(
            blocked=True,
            message="⛔ 方法论门控未通过: 需要验收场景",
            gate_results=[gr],
        )
        assert result.blocked is True
        assert "方法论门控未通过" in result.message
        assert len(result.gate_results) == 1
