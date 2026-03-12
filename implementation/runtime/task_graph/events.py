"""
EventBus integration for task graph state changes.
"""

from __future__ import annotations

import logging

log = logging.getLogger("task-graph-events")

# Event types
TASK_CREATED = "task.created"
TASK_UPDATED = "task.updated"
TASK_COMPLETED = "task.completed"
TASK_FAILED = "task.failed"
TASK_CANCELLED = "task.cancelled"
TASK_DECOMPOSED = "task.decomposed"
TASK_AUTO_COMPLETED = "task.auto_completed"


def task_event_payload(task_id: str, session_key: str, **extra) -> dict:
    """Build a standardised event payload for task graph events."""
    return {
        "task_id": task_id,
        "session_key": session_key,
        **extra,
    }
