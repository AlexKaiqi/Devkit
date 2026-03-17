"""
Methodology context builder — injects methodology gate status into agent system prompt.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from methodology.engine import MethodologyEngine

log = logging.getLogger("methodology-context")


async def build_methodology_context(engine: "MethodologyEngine", session_key: str) -> str:
    """
    Build methodology state context string for agent system prompt injection.
    Returns empty string if no active features or on error.

    Format:
    [方法论状态]
    Feature: reminder-conflict (new_capability) — 当前阶段: requirements
    ⛔ 门控 requirements→design 未通过: 新能力必须先有验收场景
      📋 参考模板: design/ontology/templates/acceptance-case.template.json
    产物清单: 无
    """
    try:
        features = await engine.get_session_features(session_key)
        if not features:
            return ""

        lines = ["[方法论状态]"]
        for feature in features:
            try:
                summary = await engine.get_feature_summary(feature.feature_id)
            except Exception as e:
                log.warning("Failed to get feature summary for %s: %s", feature.feature_id, e)
                continue

            lines.append(
                f"Feature: {summary['title']} ({summary['change_type']}) "
                f"[{summary['feature_id']}] — 当前阶段: {summary['current_phase']}"
            )

            # Show gate results for current phase
            any_gate_shown = False
            for phase_entry in summary.get("phases", []):
                if phase_entry["status"] != "current":
                    continue
                for gate in phase_entry.get("gates", []):
                    any_gate_shown = True
                    passed = gate["passed"]
                    if not passed:
                        sym = "⛔" if gate["type"] == "hard_block" else "⚠️ "
                        next_phase = _get_next_phase_name(summary, phase_entry["phase"])
                        lines.append(
                            f"  {sym} 门控 {phase_entry['phase']}→{next_phase} 未通过: {gate['message']}"
                        )
                        if gate.get("template"):
                            lines.append(f"    📋 参考模板: {gate['template']}")
                    else:
                        next_phase = _get_next_phase_name(summary, phase_entry["phase"])
                        lines.append(
                            f"  ✅ 门控 {phase_entry['phase']}→{next_phase} 通过"
                        )

            if not any_gate_shown:
                lines.append("  （当前阶段无门控要求，可自由推进）")

            # Implementation phase: inject testing guidance
            if feature.current_phase.value == "implementation":
                guidance = await _build_testing_guidance(engine, feature)
                if guidance:
                    lines.append(guidance)

        if len(lines) <= 1:
            return ""

        lines.append(
            "\n⚠️ 若门控 ⛔ 未通过，在门控满足前禁止执行写入操作（write_file/exec/code_agent）。"
            "请先完成对应产物，再调用 advance_phase 推进阶段。"
        )
        return "\n".join(lines)

    except Exception as e:
        log.warning("Failed to build methodology context: %s", e)
        return ""


async def _build_testing_guidance(engine: "MethodologyEngine", feature) -> str:
    """从 testing-methodology.yaml 读取并格式化实施步骤指引。"""
    try:
        strategy = await engine.get_testing_strategy(feature.feature_id)
        if not strategy:
            return ""

        lines = [f"\n[实施指引] {feature.title} ({feature.change_type.value})"]
        lines.append(f"测试策略: {strategy.get('description', '')}")

        # 必需测试方法
        required = strategy.get("required_approaches", [])
        if required:
            lines.append(f"必需测试方法: {', '.join(required)}")

        # 覆盖率要求
        cov = strategy.get("coverage_mandate", {})
        min_pct = cov.get("min_percent", 0)
        if min_pct:
            lines.append(f"最低覆盖率: {min_pct}%")

        # 有序步骤
        steps = strategy.get("ordered_steps", [])
        if steps:
            lines.append("\n执行步骤（请严格按顺序）:")
            for s in steps:
                step_name = s.get("step", "")
                action = s.get("action", "")
                is_hard = s.get("is_hard_block", False)
                gate = s.get("gate", "")
                note = s.get("note", "")

                block_mark = " [必须]" if is_hard else ""
                lines.append(f"  {step_name}{block_mark}")
                lines.append(f"    操作: {action}")
                if gate:
                    lines.append(f"    门控: {gate}")
                if note:
                    lines.append(f"    备注: {note}")

        # change-points 必填字段
        cp_req = strategy.get("change_point_requirements", {})
        if cp_req and cp_req.get("file"):
            fields = cp_req.get("mandatory_fields", [])
            if fields:
                lines.append(f"\nchange-points.json 必填字段: {', '.join(fields)}")
                lines.append(f"  📋 参考模板: design/ontology/templates/change-points.template.json")

        return "\n".join(lines)

    except Exception as e:
        log.warning("Failed to build testing guidance for %s: %s", feature.feature_id, e)
        return ""


def _get_next_phase_name(summary: dict, current_phase_name: str) -> str:
    """Find the next phase name after current_phase_name in phases list."""
    phases = summary.get("phases", [])
    for i, p in enumerate(phases):
        if p["phase"] == current_phase_name and i + 1 < len(phases):
            return phases[i + 1]["phase"]
    return "finalize"
