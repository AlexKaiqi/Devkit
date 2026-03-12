"""
Integration tests for Task Graph + Neo4j.

These tests require a running Neo4j instance.
Run with: .venv/bin/pytest implementation/tests/integration/test_task_graph_neo4j.py

Mark: requires Neo4j running at bolt://localhost:7687
"""

import pytest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from task_graph.graph_store import GraphStore
from task_graph.orchestrator import TaskOrchestrator
from task_graph.models import TaskNode, TaskState


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def store():
    s = GraphStore()
    try:
        await s.connect()
    except Exception:
        pytest.skip("Neo4j not available")
    yield s
    # Cleanup: delete all test tasks
    async with s._driver.session() as session:
        await session.run("MATCH (t:Task) WHERE t.session_key STARTS WITH 'test-' DETACH DELETE t")
    await s.close()


@pytest.fixture
async def orchestrator(store):
    return TaskOrchestrator(store)


@pytest.fixture
async def cleanup_session(store):
    """Yields a session key and cleans up after."""
    import uuid
    sk = f"test-{uuid.uuid4().hex[:8]}"
    yield sk
    async with store._driver.session() as session:
        await session.run("MATCH (t:Task {session_key: $sk}) DETACH DELETE t", sk=sk)


@pytest.mark.asyncio
async def test_create_and_get_task(store, cleanup_session):
    sk = cleanup_session
    task = TaskNode(title="Integration test task", session_key=sk)
    created = await store.create_task(task)
    assert created.task_id == task.task_id

    fetched = await store.get_task(task.task_id)
    assert fetched is not None
    assert fetched.title == "Integration test task"
    assert fetched.state == TaskState.QUEUED


@pytest.mark.asyncio
async def test_create_subtask_with_edge(store, cleanup_session):
    sk = cleanup_session
    parent = TaskNode(title="Parent", session_key=sk, depth=0)
    await store.create_task(parent)

    child = TaskNode(
        title="Child", session_key=sk, depth=1,
        parent_task_id=parent.task_id,
    )
    await store.create_task(child)

    children = await store.get_children(parent.task_id)
    assert len(children) == 1
    assert children[0].task_id == child.task_id


@pytest.mark.asyncio
async def test_stack_path(store, cleanup_session):
    sk = cleanup_session
    root = TaskNode(title="Root", session_key=sk, depth=0)
    await store.create_task(root)

    mid = TaskNode(title="Mid", session_key=sk, depth=1, parent_task_id=root.task_id)
    await store.create_task(mid)

    leaf = TaskNode(title="Leaf", session_key=sk, depth=2, parent_task_id=mid.task_id)
    await store.create_task(leaf)

    path = await store.get_stack_path(leaf.task_id)
    assert len(path) == 3
    assert path[0].title == "Root"
    assert path[1].title == "Mid"
    assert path[2].title == "Leaf"


@pytest.mark.asyncio
async def test_focus_task(store, cleanup_session):
    sk = cleanup_session
    root = TaskNode(title="Root", session_key=sk, state=TaskState.RUNNING, depth=0)
    await store.create_task(root)

    child = TaskNode(
        title="Deep child", session_key=sk, state=TaskState.RUNNING, depth=1,
        parent_task_id=root.task_id,
    )
    await store.create_task(child)

    focus = await store.get_focus_task(sk)
    assert focus is not None
    assert focus.task_id == child.task_id  # Deepest running


@pytest.mark.asyncio
async def test_session_root_tasks(store, cleanup_session):
    sk = cleanup_session
    r1 = TaskNode(title="Root 1", session_key=sk)
    r2 = TaskNode(title="Root 2", session_key=sk)
    await store.create_task(r1)
    await store.create_task(r2)

    roots = await store.get_session_root_tasks(sk)
    assert len(roots) == 2


@pytest.mark.asyncio
async def test_update_task(store, cleanup_session):
    sk = cleanup_session
    task = TaskNode(title="Update me", session_key=sk)
    await store.create_task(task)

    updated = await store.update_task(task.task_id, state=TaskState.RUNNING, priority=1)
    assert updated.state == TaskState.RUNNING
    assert updated.priority == 1


@pytest.mark.asyncio
async def test_auto_completion_propagation(orchestrator, store, cleanup_session):
    sk = cleanup_session

    # Create parent
    parent = await orchestrator.create_task(sk, "Parent task")

    # Decompose into 2 subtasks
    children = await orchestrator.decompose_task(
        parent.task_id,
        [{"title": "Sub 1"}, {"title": "Sub 2"}],
    )

    # Complete both subtasks
    await orchestrator.complete_task(children[0].task_id, "Done 1")
    await orchestrator.complete_task(children[1].task_id, "Done 2")

    # Parent should be auto-completed
    parent_check = await store.get_task(parent.task_id)
    assert parent_check.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_subtree(store, cleanup_session):
    sk = cleanup_session
    root = TaskNode(title="Tree root", session_key=sk)
    await store.create_task(root)

    c1 = TaskNode(title="Child 1", session_key=sk, parent_task_id=root.task_id, depth=1)
    c2 = TaskNode(title="Child 2", session_key=sk, parent_task_id=root.task_id, depth=1)
    await store.create_task(c1)
    await store.create_task(c2)

    tree = await store.get_subtree(root.task_id)
    assert tree["task"]["title"] == "Tree root"
    assert len(tree["children"]) == 2
