"""
High-level orchestration logic for the task graph.

Handles decomposition, completion propagation ("stack pop"),
failure, cancellation, and continuation.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from task_graph.graph_store import GraphStore
from task_graph.models import TaskNode, TaskState, TERMINAL_STATES
from task_graph.stack import render_task_context
from task_graph.events import (
    TASK_CREATED, TASK_UPDATED, TASK_COMPLETED, TASK_FAILED,
    TASK_CANCELLED, TASK_DECOMPOSED, TASK_AUTO_COMPLETED,
    task_event_payload,
)

log = logging.getLogger("task-graph-orchestrator")


class TaskOrchestrator:
    """Orchestrates task graph operations with auto-propagation."""

    def __init__(self, store: GraphStore, event_bus=None):
        self.store = store
        self.event_bus = event_bus

    async def _publish(self, event_type: str, session_key: str, **payload_extra):
        if self.event_bus:
            from event_bus import Event
            await self.event_bus.publish(Event(
                event_type=event_type,
                session_key=session_key,
                payload=task_event_payload(session_key=session_key, **payload_extra),
            ))

    # ── Core Operations ───────────────────────────────

    async def create_task(
        self,
        session_key: str,
        title: str,
        intent: str = "",
        risk_level: str = "low",
        parent_task_id: Optional[str] = None,
        source_channel: str = "",
        priority: int = 3,
    ) -> TaskNode:
        """Create a new task (root or subtask)."""
        depth = 0
        if parent_task_id:
            parent = await self.store.get_task(parent_task_id)
            if parent:
                depth = parent.depth + 1

        task = TaskNode(
            session_key=session_key,
            source_channel=source_channel,
            title=title,
            intent=intent,
            risk_level=risk_level,
            state=TaskState.QUEUED,
            priority=priority,
            depth=depth,
            parent_task_id=parent_task_id,
        )
        await self.store.create_task(task)
        await self._publish(TASK_CREATED, session_key, task_id=task.task_id, title=title)
        return task

    async def decompose_task(
        self,
        task_id: str,
        subtasks: list[dict],
    ) -> list[TaskNode]:
        """Decompose a task into multiple subtasks at once."""
        parent = await self.store.get_task(task_id)
        if not parent:
            raise ValueError(f"Task {task_id} not found")

        created = []
        for i, sub in enumerate(subtasks):
            child = TaskNode(
                session_key=parent.session_key,
                source_channel=parent.source_channel,
                title=sub["title"],
                intent=sub.get("intent", ""),
                risk_level=sub.get("risk_level", parent.risk_level),
                state=TaskState.QUEUED,
                priority=sub.get("priority", i + 1),
                depth=parent.depth + 1,
                parent_task_id=task_id,
            )
            await self.store.create_task(child)
            created.append(child)

        # Set parent to running if it was queued
        if parent.state == TaskState.QUEUED:
            await self.store.update_task(task_id, state=TaskState.RUNNING)

        await self._publish(
            TASK_DECOMPOSED, parent.session_key,
            task_id=task_id,
            subtask_ids=[c.task_id for c in created],
        )
        log.info("Decomposed task %s into %d subtasks", task_id[:8], len(created))
        return created

    async def complete_task(
        self,
        task_id: str,
        result_summary: str = "",
        artifacts: list[str] | None = None,
    ) -> TaskNode:
        """Mark a task as completed and trigger upward propagation."""
        now = time.time()
        updates = {
            "state": TaskState.COMPLETED,
            "completed_at": now,
        }
        if result_summary:
            updates["result_summary"] = result_summary
        if artifacts:
            updates["artifacts"] = artifacts

        task = await self.store.update_task(task_id, **updates)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        await self._publish(TASK_COMPLETED, task.session_key, task_id=task_id)

        # Auto-propagation: check if parent should also complete
        await self._propagate_completion(task_id)

        return task

    async def fail_task(self, task_id: str, error_summary: str = "") -> TaskNode:
        """Mark a task as failed."""
        updates = {"state": TaskState.FAILED}
        if error_summary:
            updates["error_summary"] = error_summary

        task = await self.store.update_task(task_id, **updates)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        await self._publish(TASK_FAILED, task.session_key, task_id=task_id, error=error_summary)
        return task

    async def update_task(
        self,
        task_id: str,
        state: Optional[str] = None,
        priority: Optional[int] = None,
        next_action: Optional[str] = None,
    ) -> TaskNode:
        """General-purpose update (pause, resume, cancel, priority change)."""
        updates = {}
        if state is not None:
            new_state = TaskState(state)
            updates["state"] = new_state
            if new_state == TaskState.CANCELLED:
                # Cascade cancel to children
                await self._cascade_cancel(task_id)
        if priority is not None:
            updates["priority"] = priority
        if next_action is not None:
            updates["next_action"] = next_action

        task = await self.store.update_task(task_id, **updates)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        event_type = TASK_CANCELLED if state == "cancelled" else TASK_UPDATED
        await self._publish(event_type, task.session_key, task_id=task_id)
        return task

    async def get_task_status(
        self,
        task_id: Optional[str] = None,
        session_key: Optional[str] = None,
    ) -> dict:
        """Get task details or session task tree."""
        if task_id:
            task = await self.store.get_task(task_id)
            if not task:
                return {"error": f"Task {task_id} not found"}
            children = await self.store.get_children(task_id)
            parent = await self.store.get_parent(task_id)
            return {
                "task": task.model_dump(),
                "children": [c.model_dump() for c in children],
                "parent_id": parent.task_id if parent else None,
            }
        elif session_key:
            root_tasks = await self.store.get_session_root_tasks(session_key)
            counts = await self.store.get_session_task_counts(session_key)
            return {
                "session_key": session_key,
                "root_tasks": [t.model_dump() for t in root_tasks],
                "counts": counts,
            }
        return {"error": "Provide either task_id or session_key"}

    # ── Context Injection ─────────────────────────────

    async def build_context(self, session_key: str) -> str:
        """Build the task context string for Context Assembly injection."""
        focus = await self.store.get_focus_task(session_key)
        stack_path = []
        if focus:
            stack_path = await self.store.get_stack_path(focus.task_id)

        root_tasks = await self.store.get_session_root_tasks(session_key)
        children_map = {}
        for rt in root_tasks:
            children_map[rt.task_id] = await self.store.get_children(rt.task_id)

        context = render_task_context(stack_path, focus, root_tasks, children_map)
        return context

    # ── Recovery ──────────────────────────────────────

    async def recover_on_startup(self) -> int:
        """Recover tasks after a restart. Returns the count of recovered tasks."""
        tasks = await self.store.get_all_non_terminal_tasks()
        recovered = 0
        for task in tasks:
            if task.state == TaskState.RUNNING:
                await self.store.update_task(task.task_id, state=TaskState.QUEUED)
                recovered += 1
                log.info("Recovered task %s: running → queued", task.task_id[:8])
        log.info("Recovery complete: %d tasks downgraded to queued", recovered)
        return recovered

    # ── Internal Helpers ──────────────────────────────

    async def _propagate_completion(self, task_id: str) -> None:
        """Check if all siblings are completed; if so, auto-complete the parent."""
        all_done, parent_id = await self.store.check_siblings_all_completed(task_id)
        if all_done and parent_id:
            parent = await self.store.get_task(parent_id)
            if parent and parent.state not in TERMINAL_STATES:
                await self.store.update_task(
                    parent_id,
                    state=TaskState.COMPLETED,
                    completed_at=time.time(),
                    result_summary="所有子任务已完成",
                )
                await self._publish(
                    TASK_AUTO_COMPLETED, parent.session_key, task_id=parent_id,
                )
                log.info("Auto-completed parent task %s", parent_id[:8])
                # Recurse upward
                await self._propagate_completion(parent_id)

    async def _cascade_cancel(self, task_id: str) -> None:
        """Cancel all non-terminal children recursively."""
        children = await self.store.get_children(task_id)
        for child in children:
            if child.state not in TERMINAL_STATES:
                await self.store.update_task(child.task_id, state=TaskState.CANCELLED)
                await self._cascade_cancel(child.task_id)
