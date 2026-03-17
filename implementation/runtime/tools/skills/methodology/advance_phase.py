"""
advance_phase skill tool — advance a Feature to the next phase.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME_DIR = Path(__file__).resolve().parents[4]
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))


async def advance_phase(args: dict, ctx=None) -> str:
    """
    Attempt to advance a Feature to the next phase.
    If gate checks fail, returns blocking reason.

    Args:
        feature_id: Feature ID
        skip_reason: (optional) If provided, skip current phase with this reason instead of checking gates
    """
    feature_id = args.get("feature_id", "").strip()
    skip_reason = args.get("skip_reason", "").strip()

    if not feature_id:
        return "[error] feature_id 参数不能为空"

    try:
        from tools import get_context
        engine = get_context("methodology_engine")
    except Exception:
        engine = None

    if engine is None:
        return "[error] 方法论引擎不可用"

    feature = await engine.get_feature(feature_id)
    if not feature:
        return f"[error] 未找到 Feature: {feature_id}"

    # Skip mode
    if skip_reason:
        updated = await engine.skip_phase(feature_id, feature.current_phase, skip_reason)
        if not updated:
            return f"[error] 跳过阶段失败"
        return (
            f"✅ 已跳过阶段 {feature.current_phase.value}\n"
            f"  理由: {skip_reason}\n"
            f"  新阶段: {updated.current_phase.value}"
        )

    # Normal advance with gate checks
    results = await engine.advance_phase(feature_id)

    # Get updated feature
    updated = await engine.get_feature(feature_id)

    # Format output
    from methodology.models import GateType
    hard_failures = [r for r in results if not r.passed and r.gate_type == GateType.hard_block]

    if hard_failures:
        lines = [f"⛔ 方法论门控未通过，无法推进阶段"]
        for r in hard_failures:
            lines.append(f"\n  ⛔ {r.gate_check}: {r.message}")
            if r.details:
                lines.append(f"     详情: {r.details}")
        lines.append(f"\n请先完成以上要求，再尝试推进阶段。")
        return "\n".join(lines)

    # Success
    soft_warns = [r for r in results if not r.passed and r.gate_type == GateType.soft_warn]
    warn_note = ""
    if soft_warns:
        warn_msgs = [f"⚠️  {r.gate_check}: {r.message}" for r in soft_warns]
        warn_note = "\n\n软警告（可继续但建议处理）:\n" + "\n".join(warn_msgs)

    new_phase = updated.current_phase.value if updated else "unknown"
    return (
        f"✅ 阶段已推进\n"
        f"  Feature: {feature.title}\n"
        f"  {feature.current_phase.value} → {new_phase}"
        + warn_note
    )


TOOL_DEF = {
    "name": "advance_phase",
    "description": (
        "将 Feature 推进到下一阶段。会运行门控检查，若 hard_block 未通过则返回阻塞原因。"
        "可选提供 skip_reason 跳过当前阶段（需有合理理由）。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "feature_id": {
                "type": "string",
                "description": "Feature ID",
            },
            "skip_reason": {
                "type": "string",
                "description": "（可选）跳过当前阶段的理由，不填则执行门控检查",
            },
        },
        "required": ["feature_id"],
    },
}
