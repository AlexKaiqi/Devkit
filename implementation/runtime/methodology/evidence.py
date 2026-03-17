"""
Evidence collector — records test results, traces, and file changes
as Evidence nodes in Neo4j, associated with Feature.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from methodology.engine import MethodologyEngine

log = logging.getLogger("methodology-evidence")


async def collect_test_result(
    engine: "MethodologyEngine",
    feature_id: str,
    output: str,
    passed: bool,
) -> bool:
    """
    Record a test execution result as Evidence for a Feature.

    Args:
        engine: MethodologyEngine instance
        feature_id: Target Feature ID
        output: Test output (trimmed to 500 chars)
        passed: Whether tests passed

    Returns True on success.
    """
    if not engine._graph_ops:
        return False
    try:
        status = "通过" if passed else "失败"
        summary = f"测试{status}: {output[:300]}"
        await engine._graph_ops.record_evidence(
            feature_id=feature_id,
            evidence_type="test_result",
            summary=summary,
        )
        return True
    except Exception as e:
        log.warning("Failed to collect test result evidence: %s", e)
        return False


async def collect_trace(
    engine: "MethodologyEngine",
    feature_id: str,
    trace_id: str,
) -> bool:
    """
    Associate a conversation trace with a Feature as Evidence.

    Args:
        engine: MethodologyEngine instance
        feature_id: Target Feature ID
        trace_id: Trace ID from agent.py

    Returns True on success.
    """
    if not engine._graph_ops:
        return False
    try:
        await engine._graph_ops.record_evidence(
            feature_id=feature_id,
            evidence_type="trace",
            summary=f"对话 trace: {trace_id}",
        )
        return True
    except Exception as e:
        log.warning("Failed to collect trace evidence: %s", e)
        return False


async def collect_file_change(
    engine: "MethodologyEngine",
    feature_id: str,
    files: list[str],
    summary: str,
) -> bool:
    """
    Record file changes as Evidence for a Feature.

    Args:
        engine: MethodologyEngine instance
        feature_id: Target Feature ID
        files: List of changed file paths
        summary: Human-readable summary of the changes

    Returns True on success.
    """
    if not engine._graph_ops:
        return False
    try:
        files_str = ", ".join(files[:5])
        if len(files) > 5:
            files_str += f" 等 {len(files)} 个文件"
        full_summary = f"{summary} ({files_str})"
        await engine._graph_ops.record_evidence(
            feature_id=feature_id,
            evidence_type="file_change",
            summary=full_summary,
            file_path=files[0] if files else "",
        )
        return True
    except Exception as e:
        log.warning("Failed to collect file change evidence: %s", e)
        return False
