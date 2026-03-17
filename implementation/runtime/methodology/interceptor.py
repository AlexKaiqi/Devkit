"""
Methodology interceptor — hard-blocks implementation tool calls when
methodology gates are not satisfied.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from methodology.models import GateType, InterceptResult

if TYPE_CHECKING:
    from methodology.engine import MethodologyEngine

log = logging.getLogger("methodology-interceptor")

# Tools that write/execute code — these are interceptable
IMPLEMENTATION_TOOLS = frozenset({
    "write_file",
    "exec",
    "code_agent",
    "edit_file",
    "run_command",
    "bash",
})

# Read-only tools — never intercepted
_READ_ONLY_TOOLS = frozenset({
    "read_file",
    "recall",
    "search",
    "grep",
    "glob",
    "list_files",
    "check_gates",
    "create_feature",
    "advance_phase",
    "link_artifact",
    "get_task_status",
    "notify",
    "timer",
})

# Phases that require implementation gate checks
_BLOCKED_PHASES = frozenset({
    "classify",
    "requirements",
    "design",
})


class MethodologyInterceptor:
    """
    Pre-execution interceptor for tool calls.
    Checks if the current session's active Features have satisfied
    methodology gates before allowing implementation tools to run.
    """

    def __init__(self, engine: "MethodologyEngine"):
        self._engine = engine

    async def check(
        self,
        tool_name: str,
        tool_args: dict,
        session_key: str,
    ) -> InterceptResult:
        """
        Check if a tool call should be blocked.

        Returns InterceptResult with blocked=True if any active Feature
        in the session has an unsatisfied hard_block gate that prevents
        moving to implementation.
        """
        # Never block read-only tools
        if tool_name in _READ_ONLY_TOOLS:
            return InterceptResult(blocked=False)

        # Only block implementation tools
        if tool_name not in IMPLEMENTATION_TOOLS:
            return InterceptResult(blocked=False)

        try:
            features = await self._engine.get_session_features(session_key)
        except Exception as e:
            log.warning("Interceptor: failed to get session features: %s", e)
            return InterceptResult(blocked=False)

        if not features:
            return InterceptResult(blocked=False)

        # Check each active feature
        block_messages = []
        all_gate_results = []

        for feature in features:
            # Only block if feature is in a pre-implementation phase
            if feature.current_phase.value not in _BLOCKED_PHASES:
                continue

            try:
                gate_results = await self._engine.check_current_gates(feature.feature_id)
            except Exception as e:
                log.warning("Interceptor: gate check failed for %s: %s", feature.feature_id, e)
                continue

            hard_failures = [
                r for r in gate_results
                if not r.passed and r.gate_type == GateType.hard_block
            ]

            if hard_failures:
                all_gate_results.extend(hard_failures)
                for failure in hard_failures:
                    block_messages.append(
                        f"Feature「{feature.title}」[{feature.feature_id}] "
                        f"阶段 {feature.current_phase.value}: {failure.message}"
                    )

        if not block_messages:
            return InterceptResult(blocked=False)

        message_parts = ["⛔ 方法论门控未通过，禁止执行写入操作\n"]
        for msg in block_messages:
            message_parts.append(f"  ⛔ {msg}")
        message_parts.append(
            "\n请先完成以上要求后，调用 advance_phase 推进阶段，再执行实现操作。"
            "\n（如需绕过检查，设置环境变量 METHODOLOGY_ENFORCEMENT=off）"
        )

        return InterceptResult(
            blocked=True,
            message="\n".join(message_parts),
            gate_results=all_gate_results,
        )
