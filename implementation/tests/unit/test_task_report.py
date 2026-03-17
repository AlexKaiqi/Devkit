"""Tests for task_report tool and colloquial task keyword activation (Feature 4)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))


def _make_orchestrator(tasks: list[dict]):
    """Create a mock orchestrator whose get_task_status returns given tasks."""
    orch = MagicMock()
    orch.get_task_status = AsyncMock(return_value={"tasks": tasks})
    return orch


@pytest.mark.asyncio
async def test_task_report_formats_running():
    """mock orchestrator → 摘要含 '进行中'"""
    import tools.skills.task.task_report as tr

    ctx = MagicMock()
    ctx.session_key = "s1"
    ctx.get = lambda k: _make_orchestrator([
        {"task_id": "t1", "title": "写报告", "state": "running", "children": []},
    ])

    result = await tr.task_report({}, ctx)
    assert "进行中" in result


@pytest.mark.asyncio
async def test_task_report_formats_completed():
    """→ 摘要含 '已完成'"""
    import tools.skills.task.task_report as tr

    ctx = MagicMock()
    ctx.session_key = "s1"
    ctx.get = lambda k: _make_orchestrator([
        {"task_id": "t2", "title": "买菜", "state": "completed", "children": []},
    ])

    result = await tr.task_report({}, ctx)
    assert "已完成" in result


@pytest.mark.asyncio
async def test_task_report_handles_empty():
    """空会话 → '暂无'"""
    import tools.skills.task.task_report as tr

    ctx = MagicMock()
    ctx.session_key = "s1"
    ctx.get = lambda k: _make_orchestrator([])

    result = await tr.task_report({}, ctx)
    assert "暂无" in result


@pytest.mark.asyncio
async def test_task_report_handles_failed():
    """失败任务 → 摘要含错误描述"""
    import tools.skills.task.task_report as tr

    ctx = MagicMock()
    ctx.session_key = "s1"
    ctx.get = lambda k: _make_orchestrator([
        {"task_id": "t3", "title": "分析数据", "state": "failed",
         "error": "数据源不可达", "children": []},
    ])

    result = await tr.task_report({}, ctx)
    assert "失败" in result
    assert "数据源不可达" in result


def test_colloquial_keywords_activate_task_skill():
    """'做完了吗' → task skill 激活"""
    from tools import discover_tools, get_active_skills, _SKILLS
    discover_tools()

    skill_names = {s.name for s in get_active_skills("做完了吗")}
    assert "task" in skill_names, f"task skill not activated for '做完了吗', active: {skill_names}"
