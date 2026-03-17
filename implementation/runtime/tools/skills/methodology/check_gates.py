"""
check_gates skill tool — check methodology gates for a Feature.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME_DIR = Path(__file__).resolve().parents[4]
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))


async def check_gates(args: dict, ctx=None) -> str:
    """
    Check methodology gate status for a Feature.

    Args:
        feature_id: Feature ID (from create_feature)
    """
    feature_id = args.get("feature_id", "").strip()
    if not feature_id:
        return "[error] feature_id 参数不能为空"

    try:
        from tools import get_context
        engine = get_context("methodology_engine")
    except Exception:
        engine = None

    if engine is None:
        return "[error] 方法论引擎不可用"

    summary = await engine.get_feature_summary(feature_id)
    if not summary:
        return f"[error] 未找到 Feature: {feature_id}"

    lines = [
        f"[方法论状态] Feature: {summary['title']} ({summary['change_type']})",
        f"当前阶段: {summary['current_phase']}",
        "",
    ]

    for phase_entry in summary.get("phases", []):
        phase = phase_entry["phase"]
        status = phase_entry["status"]
        skip = phase_entry.get("skip_reason", "")

        if status == "completed":
            sym = "✅"
        elif status == "current":
            sym = "▶ "
        else:
            sym = "⏸ "

        skip_note = f" [已跳过: {skip}]" if skip else ""
        lines.append(f"  {sym} {phase}{skip_note}")

        # Show gate results for current phase
        gates = phase_entry.get("gates", [])
        for gate in gates:
            passed = gate["passed"]
            gate_sym = "✅" if passed else ("⛔" if gate["type"] == "hard_block" else "⚠️ ")
            status_str = "通过" if passed else "未通过"
            lines.append(f"      {gate_sym} {gate['check']} [{status_str}]")
            if not passed and gate.get("message"):
                lines.append(f"         → {gate['message']}")
            if not passed and gate.get("template"):
                lines.append(f"         📋 参考模板: {gate['template']}")

    return "\n".join(lines)


TOOL_DEF = {
    "name": "check_gates",
    "description": "检查指定 Feature 当前阶段的方法论门控状态，确认是否可以推进到下一阶段",
    "parameters": {
        "type": "object",
        "properties": {
            "feature_id": {
                "type": "string",
                "description": "Feature ID（由 create_feature 返回）",
            },
        },
        "required": ["feature_id"],
    },
}
