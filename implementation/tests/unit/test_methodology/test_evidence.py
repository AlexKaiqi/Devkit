"""Unit tests for evidence collection."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.evidence import collect_test_result, collect_trace, collect_file_change


def _make_engine_with_ops(mock_record=None):
    """Create a mock engine with a mock _graph_ops."""
    engine = MagicMock()
    graph_ops = MagicMock()
    if mock_record is None:
        graph_ops.record_evidence = AsyncMock(return_value=None)
    else:
        graph_ops.record_evidence = mock_record
    engine._graph_ops = graph_ops
    return engine


@pytest.mark.asyncio
class TestCollectTestResult:
    async def test_records_passed(self):
        engine = _make_engine_with_ops()
        result = await collect_test_result(engine, "feat-001", "5 passed", passed=True)
        assert result is True
        engine._graph_ops.record_evidence.assert_called_once()
        call_kwargs = engine._graph_ops.record_evidence.call_args[1]
        assert call_kwargs["feature_id"] == "feat-001"
        assert call_kwargs["evidence_type"] == "test_result"
        assert "通过" in call_kwargs["summary"]

    async def test_records_failed(self):
        engine = _make_engine_with_ops()
        result = await collect_test_result(engine, "feat-001", "2 failed", passed=False)
        assert result is True
        call_kwargs = engine._graph_ops.record_evidence.call_args[1]
        assert "失败" in call_kwargs["summary"]

    async def test_no_graph_ops_returns_false(self):
        engine = MagicMock()
        engine._graph_ops = None
        result = await collect_test_result(engine, "feat-001", "output", passed=True)
        assert result is False

    async def test_exception_returns_false(self):
        engine = _make_engine_with_ops(
            mock_record=AsyncMock(side_effect=RuntimeError("db error"))
        )
        result = await collect_test_result(engine, "feat-001", "output", passed=True)
        assert result is False


@pytest.mark.asyncio
class TestCollectTrace:
    async def test_records_trace(self):
        engine = _make_engine_with_ops()
        result = await collect_trace(engine, "feat-001", "trace-abc")
        assert result is True
        call_kwargs = engine._graph_ops.record_evidence.call_args[1]
        assert call_kwargs["evidence_type"] == "trace"
        assert "trace-abc" in call_kwargs["summary"]

    async def test_no_graph_ops_returns_false(self):
        engine = MagicMock()
        engine._graph_ops = None
        result = await collect_trace(engine, "feat-001", "trace-id")
        assert result is False


@pytest.mark.asyncio
class TestCollectFileChange:
    async def test_records_file_change(self):
        engine = _make_engine_with_ops()
        files = ["implementation/runtime/agent.py", "design/decisions/test.md"]
        result = await collect_file_change(engine, "feat-001", files, "Added methodology integration")
        assert result is True
        call_kwargs = engine._graph_ops.record_evidence.call_args[1]
        assert call_kwargs["evidence_type"] == "file_change"
        assert "agent.py" in call_kwargs["summary"]

    async def test_truncates_long_file_list(self):
        engine = _make_engine_with_ops()
        files = [f"file{i}.py" for i in range(10)]
        result = await collect_file_change(engine, "feat-001", files, "Many files changed")
        assert result is True
        call_kwargs = engine._graph_ops.record_evidence.call_args[1]
        assert "10 个文件" in call_kwargs["summary"]

    async def test_empty_files_list(self):
        engine = _make_engine_with_ops()
        result = await collect_file_change(engine, "feat-001", [], "No files")
        assert result is True
