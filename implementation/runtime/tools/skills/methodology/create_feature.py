"""
create_feature skill tool — create a new methodology Feature.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_RUNTIME_DIR = Path(__file__).resolve().parents[4]
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))


async def create_feature(args: dict, ctx=None) -> str:
    """
    Create a new methodology Feature to track a change through the AI-native dev workflow.

    Args:
        title: Feature title (e.g., "提醒冲突检测")
        change_type: One of: new_capability, behavior_change, bug_fix, refactoring, doc_revision, eval_asset
        session_key: (optional) Session key to associate with this Feature
    """
    title = args.get("title", "").strip()
    change_type_str = args.get("change_type", "").strip()
    session_key = args.get("session_key", "") or (ctx.session_key if ctx else "")

    if not title:
        return "[error] title 参数不能为空"
    if not change_type_str:
        return "[error] change_type 参数不能为空，可选值: new_capability, behavior_change, bug_fix, refactoring, doc_revision, eval_asset"

    try:
        from methodology.models import ChangeType
        change_type = ChangeType(change_type_str)
    except ValueError:
        return f"[error] 未知的 change_type: {change_type_str}，可选值: {', '.join(ct.value for ct in __import__('methodology.models', fromlist=['ChangeType']).ChangeType)}"

    try:
        from tools import get_context
        engine = get_context("methodology_engine")
    except Exception:
        engine = None

    if engine is None:
        # Fallback: show what would be created
        return (
            f"⚠️ 方法论引擎不可用（Neo4j 可能未运行），无法持久化 Feature。\n"
            f"如需使用，请确保 Neo4j 运行后重启服务。\n\n"
            f"如果只需静态检查，请使用 CLI:\n"
            f".venv/bin/python -m implementation.runtime.methodology.cli check "
            f"--feature <slug> --change-type {change_type_str}"
        )

    feature = await engine.create_feature(
        title=title,
        change_type=change_type,
        session_key=session_key,
    )

    # Get the mandatory path for display
    from methodology.ontology import get_ontology
    ontology = get_ontology()
    path = ontology.get_mandatory_path(change_type)
    phases_str = " → ".join(p.value for p in path.phases) if path else "N/A"

    return (
        f"✅ Feature 已创建\n"
        f"  ID: {feature.feature_id}\n"
        f"  标题: {feature.title}\n"
        f"  类型: {feature.change_type.value}\n"
        f"  当前阶段: {feature.current_phase.value}\n"
        f"  路径: {phases_str}\n\n"
        f"接下来请按方法论推进各阶段。使用 `check_gates` 检查门控状态。"
    )


TOOL_DEF = {
    "name": "create_feature",
    "description": (
        "创建一个新的方法论 Feature，用于跟踪变更在 AI 原生开发工作流中的进展。"
        "开始任何新功能、行为变更、重构等工作时调用此工具。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Feature 标题，描述这次变更的内容（中文）",
            },
            "change_type": {
                "type": "string",
                "enum": ["new_capability", "behavior_change", "bug_fix", "refactoring", "doc_revision", "eval_asset"],
                "description": "变更类型",
            },
            "session_key": {
                "type": "string",
                "description": "关联的会话 key（可选）",
            },
        },
        "required": ["title", "change_type"],
    },
}
