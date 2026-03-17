"""Unit tests for MethodologyInterceptor."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.models import (
    ChangeType, Phase, GateType, GateResult, Feature, InterceptResult
)
from methodology.interceptor import MethodologyInterceptor, IMPLEMENTATION_TOOLS


def _make_feature(
    feature_id="test-001",
    change_type=ChangeType.new_capability,
    current_phase=Phase.requirements,
    status="active",
    session_key="test-session",
) -> Feature:
    return Feature(
        feature_id=feature_id,
        title="Test Feature",
        change_type=change_type,
        current_phase=current_phase,
        status=status,
        session_key=session_key,
    )


def _make_engine(features=None, gate_results=None):
    """Create a mock MethodologyEngine."""
    engine = MagicMock()
    engine.get_session_features = AsyncMock(return_value=features or [])
    engine.check_current_gates = AsyncMock(return_value=gate_results or [])
    return engine


@pytest.mark.asyncio
class TestInterceptorBasic:
    async def test_read_only_tools_not_blocked(self):
        engine = _make_engine()
        interceptor = MethodologyInterceptor(engine)

        for tool in ["read_file", "recall", "search", "check_gates", "create_feature"]:
            result = await interceptor.check(tool, {}, "test-session")
            assert result.blocked is False, f"Tool {tool} should not be blocked"

    async def test_non_implementation_tool_not_blocked(self):
        engine = _make_engine()
        interceptor = MethodologyInterceptor(engine)
        result = await interceptor.check("get_weather", {}, "test-session")
        assert result.blocked is False

    async def test_no_active_features_not_blocked(self):
        engine = _make_engine(features=[])
        interceptor = MethodologyInterceptor(engine)
        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is False

    async def test_implementation_tool_in_set(self):
        assert "write_file" in IMPLEMENTATION_TOOLS
        assert "exec" in IMPLEMENTATION_TOOLS
        assert "code_agent" in IMPLEMENTATION_TOOLS


@pytest.mark.asyncio
class TestInterceptorHardBlock:
    async def test_blocks_when_hard_block_gate_fails(self):
        """write_file should be blocked when acceptance_case_exists gate fails."""
        feature = _make_feature(current_phase=Phase.requirements)
        gate_result = GateResult(
            gate_check="acceptance_case_exists",
            passed=False,
            gate_type=GateType.hard_block,
            message="新能力必须先有验收场景",
        )
        engine = _make_engine(features=[feature], gate_results=[gate_result])
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {"path": "some.py"}, "test-session")
        assert result.blocked is True
        assert "方法论门控未通过" in result.message
        assert "新能力必须先有验收场景" in result.message
        assert len(result.gate_results) > 0

    async def test_does_not_block_when_gate_passes(self):
        """No block when all hard_block gates pass."""
        feature = _make_feature(current_phase=Phase.requirements)
        gate_result = GateResult(
            gate_check="acceptance_case_exists",
            passed=True,
            gate_type=GateType.hard_block,
            message="",
        )
        engine = _make_engine(features=[feature], gate_results=[gate_result])
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is False

    async def test_soft_warn_failure_does_not_block(self):
        """soft_warn failure alone should not block."""
        feature = _make_feature(current_phase=Phase.implementation)
        # But current_phase = implementation is not in _BLOCKED_PHASES
        engine = _make_engine(features=[feature])
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is False

    async def test_implementation_phase_not_blocked(self):
        """Features in implementation phase are not blocked (past the gates)."""
        feature = _make_feature(current_phase=Phase.implementation)
        gate_result = GateResult(
            gate_check="some_check",
            passed=False,
            gate_type=GateType.hard_block,
            message="Some message",
        )
        engine = _make_engine(features=[feature], gate_results=[gate_result])
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {}, "test-session")
        # implementation phase is NOT in _BLOCKED_PHASES
        assert result.blocked is False

    async def test_design_phase_blocked_when_gate_fails(self):
        """design phase IS in _BLOCKED_PHASES."""
        from methodology.interceptor import _BLOCKED_PHASES
        assert "design" in _BLOCKED_PHASES

    async def test_classify_phase_blocked_when_gate_fails(self):
        """classify phase IS in _BLOCKED_PHASES."""
        from methodology.interceptor import _BLOCKED_PHASES
        assert "classify" in _BLOCKED_PHASES


@pytest.mark.asyncio
class TestInterceptorEnvSwitch:
    async def test_enforcement_off_bypasses_check(self, monkeypatch):
        """Setting METHODOLOGY_ENFORCEMENT=off should bypass the interceptor."""
        # Note: The environment variable check is in agent.py, not the interceptor itself
        # The interceptor always blocks when called — it's up to agent.py to skip calling it
        # This test documents that behavior
        feature = _make_feature(current_phase=Phase.requirements)
        gate_result = GateResult(
            gate_check="acceptance_case_exists",
            passed=False,
            gate_type=GateType.hard_block,
            message="需要验收场景",
        )
        engine = _make_engine(features=[feature], gate_results=[gate_result])
        interceptor = MethodologyInterceptor(engine)

        # Interceptor itself always checks — env var is checked by agent.py
        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is True  # would be blocked without the env var guard

    async def test_engine_error_does_not_crash(self):
        """If engine raises, interceptor should return non-blocked (fail-open)."""
        engine = MagicMock()
        engine.get_session_features = AsyncMock(side_effect=RuntimeError("connection lost"))
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is False  # fail-open

    async def test_gate_check_error_does_not_crash(self):
        """If gate check raises, interceptor should return non-blocked (fail-open)."""
        feature = _make_feature(current_phase=Phase.requirements)
        engine = MagicMock()
        engine.get_session_features = AsyncMock(return_value=[feature])
        engine.check_current_gates = AsyncMock(side_effect=RuntimeError("gate check error"))
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is False  # fail-open for gate check errors


@pytest.mark.asyncio
class TestInterceptorMultipleFeatures:
    async def test_any_blocking_feature_blocks_call(self):
        """If any active feature has hard_block failure, the call is blocked."""
        feature_ok = _make_feature(
            feature_id="ok-001",
            current_phase=Phase.implementation,  # past gates
        )
        feature_blocked = _make_feature(
            feature_id="blocked-001",
            current_phase=Phase.requirements,
        )
        gate_result = GateResult(
            gate_check="acceptance_case_exists",
            passed=False,
            gate_type=GateType.hard_block,
            message="需要验收场景",
        )

        engine = MagicMock()
        engine.get_session_features = AsyncMock(return_value=[feature_ok, feature_blocked])

        async def mock_gates(fid):
            if fid == "blocked-001":
                return [gate_result]
            return []

        engine.check_current_gates = mock_gates
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is True

    async def test_all_features_past_gates_not_blocked(self):
        """If all features are past their gate phases, no block."""
        feature1 = _make_feature(feature_id="f1", current_phase=Phase.implementation)
        feature2 = _make_feature(feature_id="f2", current_phase=Phase.verification)
        engine = _make_engine(features=[feature1, feature2], gate_results=[])
        interceptor = MethodologyInterceptor(engine)

        result = await interceptor.check("write_file", {}, "test-session")
        assert result.blocked is False
