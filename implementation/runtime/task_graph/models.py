"""
Pydantic data models for the Task Graph system.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    NEEDS_CLARIFICATION = "needs_clarification"
    NEEDS_CONFIRMATION = "needs_confirmation"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}
ACTIVE_STATES = {TaskState.QUEUED, TaskState.RUNNING, TaskState.WAITING_EXTERNAL, TaskState.WAITING_USER}


class TaskNode(BaseModel):
    """A single task node in the graph."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_key: str = ""
    source_channel: str = ""
    title: str = ""
    intent: str = ""
    risk_level: str = "low"
    state: TaskState = TaskState.QUEUED
    priority: int = 3  # 1=highest, 5=lowest
    depth: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    next_action: Optional[str] = None
    artifacts: list[str] = Field(default_factory=list)
    result_summary: Optional[str] = None
    error_summary: Optional[str] = None

    # Relationship references (not stored in Neo4j node properties)
    parent_task_id: Optional[str] = None
    children_ids: list[str] = Field(default_factory=list)

    def to_neo4j_props(self) -> dict:
        """Convert to a flat dict for Neo4j node properties."""
        return {
            "task_id": self.task_id,
            "session_key": self.session_key,
            "source_channel": self.source_channel,
            "title": self.title,
            "intent": self.intent,
            "risk_level": self.risk_level,
            "state": self.state.value,
            "priority": self.priority,
            "depth": self.depth,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "next_action": self.next_action,
            "artifacts": self.artifacts,
            "result_summary": self.result_summary,
            "error_summary": self.error_summary,
        }

    @classmethod
    def from_neo4j_record(cls, record: dict) -> TaskNode:
        """Create from a Neo4j record dict."""
        state_val = record.get("state", "queued")
        return cls(
            task_id=record["task_id"],
            session_key=record.get("session_key", ""),
            source_channel=record.get("source_channel", ""),
            title=record.get("title", ""),
            intent=record.get("intent", ""),
            risk_level=record.get("risk_level", "low"),
            state=TaskState(state_val),
            priority=record.get("priority", 3),
            depth=record.get("depth", 0),
            created_at=record.get("created_at", 0),
            updated_at=record.get("updated_at", 0),
            completed_at=record.get("completed_at"),
            next_action=record.get("next_action"),
            artifacts=record.get("artifacts") or [],
            result_summary=record.get("result_summary"),
            error_summary=record.get("error_summary"),
        )


class TaskStack(BaseModel):
    """The stack path from root to current focus."""

    path: list[TaskNode] = Field(default_factory=list)
    focus: Optional[TaskNode] = None

    @property
    def root(self) -> Optional[TaskNode]:
        return self.path[0] if self.path else None

    @property
    def depth(self) -> int:
        return len(self.path)


class SessionTaskSummary(BaseModel):
    """Summary of all root tasks in a session."""

    session_key: str
    root_tasks: list[TaskNode] = Field(default_factory=list)
    total_count: int = 0
    completed_count: int = 0
    running_count: int = 0
