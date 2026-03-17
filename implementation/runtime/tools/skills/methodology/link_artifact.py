"""
link_artifact skill tool — link an artifact to a Feature.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME_DIR = Path(__file__).resolve().parents[4]
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))


async def link_artifact(args: dict, ctx=None) -> str:
    """
    Link an artifact file to a Feature.

    Args:
        feature_id: Feature ID
        artifact_type: One of: acceptance_case, design_decision
        file_path: Relative path from Devkit root (e.g., "requirements/acceptance/my-feature.json")
        title: (optional) Artifact title
    """
    feature_id = args.get("feature_id", "").strip()
    artifact_type = args.get("artifact_type", "").strip()
    file_path = args.get("file_path", "").strip()
    title = args.get("title", "").strip()

    if not feature_id:
        return "[error] feature_id 参数不能为空"
    if not artifact_type:
        return "[error] artifact_type 参数不能为空（acceptance_case 或 design_decision）"
    if artifact_type not in ("acceptance_case", "design_decision"):
        return f"[error] 未知的 artifact_type: {artifact_type}，可选: acceptance_case, design_decision"
    if not file_path:
        return "[error] file_path 参数不能为空"

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

    success = await engine.link_artifact(feature_id, artifact_type, file_path, title)
    if not success:
        return f"[error] 关联产物失败"

    type_cn = {"acceptance_case": "验收场景", "design_decision": "设计决策"}.get(artifact_type, artifact_type)
    return (
        f"✅ 已关联{type_cn}\n"
        f"  Feature: {feature.title} ({feature_id})\n"
        f"  文件: {file_path}"
    )


TOOL_DEF = {
    "name": "link_artifact",
    "description": "将验收场景文件或设计决策文件关联到 Feature，用于跟踪产物完成情况",
    "parameters": {
        "type": "object",
        "properties": {
            "feature_id": {
                "type": "string",
                "description": "Feature ID",
            },
            "artifact_type": {
                "type": "string",
                "enum": ["acceptance_case", "design_decision"],
                "description": "产物类型",
            },
            "file_path": {
                "type": "string",
                "description": "产物文件路径（相对 Devkit 根目录，如 requirements/acceptance/my-feature.json）",
            },
            "title": {
                "type": "string",
                "description": "产物标题（可选）",
            },
        },
        "required": ["feature_id", "artifact_type", "file_path"],
    },
}
