"""
Unit tests for the Task Graph system — models, stack rendering, orchestrator logic.

These tests mock Neo4j and test pure Python logic only.
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path

# Add runtime to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from task_graph.models import TaskNode, TaskState, TaskStack, TERMINAL_STATES, ACTIVE_STATES
from task_graph.stack import render_stack_path, render_focus_details, render_task_context


# ── Model Tests ──────────────────────────────────────

class TestTaskNode:
    def test_default_task_node(self):
        node = TaskNode(title="Test task", session_key="test-session")
        assert node.title == "Test task"
        assert node.state == TaskState.QUEUED
        assert node.priority == 3
        assert node.depth == 0
        assert node.task_id  # UUID generated
        assert node.created_at > 0

    def test_to_neo4j_props(self):
        node = TaskNode(
            task_id="abc-123",
            session_key="s1",
            title="Do thing",
            state=TaskState.RUNNING,
        )
        props = node.to_neo4j_props()
        assert props["task_id"] == "abc-123"
        assert props["state"] == "running"
        assert props["session_key"] == "s1"
        assert "parent_task_id" not in props
        assert "children_ids" not in props

    def test_from_neo4j_record(self):
        record = {
            "task_id": "xyz-789",
            "session_key": "s2",
            "title": "Read files",
            "state": "completed",
            "priority": 1,
            "depth": 2,
            "created_at": 1000.0,
            "updated_at": 2000.0,
            "completed_at": 2000.0,
        }
        node = TaskNode.from_neo4j_record(record)
        assert node.task_id == "xyz-789"
        assert node.state == TaskState.COMPLETED
        assert node.priority == 1
        assert node.depth == 2

    def test_terminal_states(self):
        assert TaskState.COMPLETED in TERMINAL_STATES
        assert TaskState.FAILED in TERMINAL_STATES
        assert TaskState.CANCELLED in TERMINAL_STATES
        assert TaskState.RUNNING not in TERMINAL_STATES

    def test_active_states(self):
        assert TaskState.QUEUED in ACTIVE_STATES
        assert TaskState.RUNNING in ACTIVE_STATES
        assert TaskState.COMPLETED not in ACTIVE_STATES


class TestTaskStack:
    def test_empty_stack(self):
        stack = TaskStack()
        assert stack.root is None
        assert stack.focus is None
        assert stack.depth == 0

    def test_stack_with_path(self):
        root = TaskNode(title="Root", depth=0)
        child = TaskNode(title="Child", depth=1)
        stack = TaskStack(path=[root, child], focus=child)
        assert stack.root.title == "Root"
        assert stack.focus.title == "Child"
        assert stack.depth == 2


# ── Stack Rendering Tests ────────────────────────────

class TestStackRendering:
    def test_render_empty_path(self):
        result = render_stack_path([], None)
        assert result == ""

    def test_render_single_root(self):
        root = TaskNode(title="根任务", state=TaskState.RUNNING, task_id="root-1")
        result = render_stack_path([root], root)
        assert "[root] 根任务 (running) ← 当前焦点" in result

    def test_render_nested_path(self):
        root = TaskNode(title="整理论文", state=TaskState.RUNNING, task_id="r1")
        child = TaskNode(title="筛选ML相关", state=TaskState.RUNNING, task_id="c1")
        result = render_stack_path([root, child], child)
        assert "[root] 整理论文 (running)" in result
        assert "└─ 筛选ML相关 (running) ← 当前焦点" in result

    def test_render_focus_details(self):
        focus = TaskNode(
            task_id="abc12345-full-uuid",
            title="筛选论文",
            state=TaskState.RUNNING,
            next_action="读取下一个 PDF",
        )
        result = render_focus_details(focus)
        assert "abc12345" in result
        assert "筛选论文" in result
        assert "running" in result
        assert "读取下一个 PDF" in result

    def test_render_focus_none(self):
        result = render_focus_details(None)
        assert "无活跃任务" in result

    def test_render_full_context(self):
        root = TaskNode(title="根任务", state=TaskState.RUNNING, task_id="r1")
        child = TaskNode(title="子任务", state=TaskState.RUNNING, task_id="c1")
        result = render_task_context(
            stack_path=[root, child],
            focus=child,
            root_tasks=[root],
            children_map={"r1": [child]},
        )
        assert "当前任务上下文" in result
        assert "任务栈" in result
        assert "当前焦点" in result
        assert "会话任务总览" in result


# ── Orchestrator Tests (mocked store) ────────────────

class TestOrchestrator:
    @pytest.fixture
    def mock_store(self):
        store = AsyncMock()
        store.create_task = AsyncMock(side_effect=lambda t: t)
        store.get_task = AsyncMock(return_value=None)
        store.update_task = AsyncMock()
        store.get_children = AsyncMock(return_value=[])
        store.get_focus_task = AsyncMock(return_value=None)
        store.get_session_root_tasks = AsyncMock(return_value=[])
        store.get_stack_path = AsyncMock(return_value=[])
        store.check_siblings_all_completed = AsyncMock(return_value=(False, None))
        store.get_all_non_terminal_tasks = AsyncMock(return_value=[])
        store.get_session_task_counts = AsyncMock(return_value={"total": 0, "completed": 0, "running": 0, "by_state": {}})
        store.get_parent = AsyncMock(return_value=None)
        return store

    @pytest.fixture
    def orchestrator(self, mock_store):
        from task_graph.orchestrator import TaskOrchestrator
        return TaskOrchestrator(mock_store, event_bus=None)

    @pytest.mark.asyncio
    async def test_create_root_task(self, orchestrator, mock_store):
        task = await orchestrator.create_task(
            session_key="test-session",
            title="Test Task",
            intent="Testing",
        )
        assert task.title == "Test Task"
        assert task.state == TaskState.QUEUED
        assert task.depth == 0
        mock_store.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_child_task(self, orchestrator, mock_store):
        parent = TaskNode(task_id="parent-1", title="Parent", depth=0)
        mock_store.get_task.return_value = parent

        task = await orchestrator.create_task(
            session_key="test-session",
            title="Child Task",
            parent_task_id="parent-1",
        )
        assert task.depth == 1
        assert task.parent_task_id == "parent-1"

    @pytest.mark.asyncio
    async def test_decompose_task(self, orchestrator, mock_store):
        parent = TaskNode(
            task_id="p1", title="Parent", session_key="s1",
            state=TaskState.QUEUED, depth=0,
        )
        mock_store.get_task.return_value = parent

        children = await orchestrator.decompose_task(
            task_id="p1",
            subtasks=[
                {"title": "Sub 1", "intent": "Do first thing"},
                {"title": "Sub 2", "intent": "Do second thing"},
            ],
        )
        assert len(children) == 2
        assert children[0].title == "Sub 1"
        assert children[1].title == "Sub 2"
        assert children[0].depth == 1
        # Parent should be set to running
        mock_store.update_task.assert_called()

    @pytest.mark.asyncio
    async def test_complete_task(self, orchestrator, mock_store):
        completed = TaskNode(
            task_id="t1", title="Done", state=TaskState.COMPLETED,
            session_key="s1",
        )
        mock_store.update_task.return_value = completed

        task = await orchestrator.complete_task("t1", result_summary="All done")
        assert task.state == TaskState.COMPLETED

    @pytest.mark.asyncio
    async def test_auto_propagation(self, orchestrator, mock_store):
        """When all siblings complete, parent should auto-complete."""
        completed_child = TaskNode(task_id="c1", title="Child", state=TaskState.COMPLETED, session_key="s1")
        parent = TaskNode(task_id="p1", title="Parent", state=TaskState.RUNNING, session_key="s1")

        mock_store.update_task.return_value = completed_child
        # First call: child's siblings all done → parent auto-completes
        # Second call: parent has no parent → stops recursion
        mock_store.check_siblings_all_completed.side_effect = [
            (True, "p1"),
            (False, None),
        ]
        mock_store.get_task.return_value = parent

        await orchestrator.complete_task("c1")

        # Parent should have been updated to completed
        calls = mock_store.update_task.call_args_list
        # At least 2 calls: one for the child, one for the parent auto-completion
        assert len(calls) >= 2

    @pytest.mark.asyncio
    async def test_fail_task(self, orchestrator, mock_store):
        failed = TaskNode(task_id="t1", title="Failed", state=TaskState.FAILED, session_key="s1")
        mock_store.update_task.return_value = failed

        task = await orchestrator.fail_task("t1", error_summary="Something broke")
        assert task.state == TaskState.FAILED

    @pytest.mark.asyncio
    async def test_recovery(self, orchestrator, mock_store):
        running_task = TaskNode(task_id="r1", title="Was Running", state=TaskState.RUNNING)
        queued_task = TaskNode(task_id="q1", title="Was Queued", state=TaskState.QUEUED)
        mock_store.get_all_non_terminal_tasks.return_value = [running_task, queued_task]

        recovered = await orchestrator.recover_on_startup()
        assert recovered == 1  # Only running task gets downgraded

    @pytest.mark.asyncio
    async def test_build_empty_context(self, orchestrator, mock_store):
        context = await orchestrator.build_context("empty-session")
        assert "当前任务上下文" in context
        assert "无活跃任务" in context
