"""
Neo4j async connection and Cypher operation wrappers for the Task Graph.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from neo4j import AsyncGraphDatabase, AsyncDriver

from task_graph.models import TaskNode, TaskState, TERMINAL_STATES

log = logging.getLogger("task-graph-store")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "devkit2026")


class GraphStore:
    """Async Neo4j operations for the task graph."""

    def __init__(
        self,
        uri: str = "",
        user: str = "",
        password: str = "",
    ):
        self._uri = uri or NEO4J_URI
        self._user = user or NEO4J_USER
        self._password = password or NEO4J_PASSWORD
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        """Establish the Neo4j connection and ensure indexes exist."""
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        # Verify connectivity
        await self._driver.verify_connectivity()
        log.info("Connected to Neo4j at %s", self._uri)
        await self._ensure_indexes()

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None
            log.info("Neo4j connection closed")

    async def _ensure_indexes(self) -> None:
        async with self._driver.session() as session:
            for cypher in [
                "CREATE INDEX task_id_idx IF NOT EXISTS FOR (t:Task) ON (t.task_id)",
                "CREATE INDEX task_session_idx IF NOT EXISTS FOR (t:Task) ON (t.session_key)",
                "CREATE INDEX task_state_idx IF NOT EXISTS FOR (t:Task) ON (t.state)",
                # Feature nodes for Methodology Ontology Enforcement
                "CREATE INDEX feature_id_idx IF NOT EXISTS FOR (f:Feature) ON (f.feature_id)",
                "CREATE INDEX feature_session_idx IF NOT EXISTS FOR (f:Feature) ON (f.session_key)",
                "CREATE INDEX feature_status_idx IF NOT EXISTS FOR (f:Feature) ON (f.status)",
            ]:
                await session.run(cypher)
        log.info("Neo4j indexes ensured")

    # ── CRUD ──────────────────────────────────────────

    async def create_task(self, task: TaskNode) -> TaskNode:
        """Create a Task node. If parent_task_id is set, also create SUBTASK_OF edge."""
        async with self._driver.session() as session:
            props = task.to_neo4j_props()
            await session.run(
                "CREATE (t:Task $props)",
                props=props,
            )
            if task.parent_task_id:
                await session.run(
                    """
                    MATCH (child:Task {task_id: $child_id})
                    MATCH (parent:Task {task_id: $parent_id})
                    CREATE (child)-[:SUBTASK_OF]->(parent)
                    """,
                    child_id=task.task_id,
                    parent_id=task.parent_task_id,
                )
        log.info("Created task %s: %s", task.task_id[:8], task.title)
        return task

    async def get_task(self, task_id: str) -> Optional[TaskNode]:
        """Fetch a single task by ID."""
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (t:Task {task_id: $tid}) RETURN t",
                tid=task_id,
            )
            record = await result.single()
            if not record:
                return None
            return TaskNode.from_neo4j_record(dict(record["t"]))

    async def update_task(self, task_id: str, **updates) -> Optional[TaskNode]:
        """Update task properties. Returns the updated task."""
        updates["updated_at"] = time.time()
        set_clauses = ", ".join(f"t.{k} = ${k}" for k in updates)
        # Convert enums to values
        params = {}
        for k, v in updates.items():
            params[k] = v.value if isinstance(v, TaskState) else v

        async with self._driver.session() as session:
            result = await session.run(
                f"MATCH (t:Task {{task_id: $tid}}) SET {set_clauses} RETURN t",
                tid=task_id,
                **params,
            )
            record = await result.single()
            if not record:
                return None
            return TaskNode.from_neo4j_record(dict(record["t"]))

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task and all its relationships."""
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (t:Task {task_id: $tid}) DETACH DELETE t RETURN count(t) AS cnt",
                tid=task_id,
            )
            record = await result.single()
            return record and record["cnt"] > 0

    # ── Relationships ─────────────────────────────────

    async def add_subtask_edge(self, child_id: str, parent_id: str) -> None:
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (c:Task {task_id: $cid})
                MATCH (p:Task {task_id: $pid})
                MERGE (c)-[:SUBTASK_OF]->(p)
                """,
                cid=child_id, pid=parent_id,
            )

    async def add_depends_on_edge(self, dependent_id: str, dependency_id: str) -> None:
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (d:Task {task_id: $did})
                MATCH (dep:Task {task_id: $depid})
                MERGE (d)-[:DEPENDS_ON]->(dep)
                """,
                did=dependent_id, depid=dependency_id,
            )

    async def add_continuation_edge(self, new_id: str, old_id: str) -> None:
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (n:Task {task_id: $nid})
                MATCH (o:Task {task_id: $oid})
                MERGE (n)-[:CONTINUATION_OF]->(o)
                """,
                nid=new_id, oid=old_id,
            )

    # ── Graph Queries ─────────────────────────────────

    async def get_stack_path(self, task_id: str) -> list[TaskNode]:
        """Get the path from a task up to the root via SUBTASK_OF."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH path = (t:Task {task_id: $tid})-[:SUBTASK_OF*0..]->(root:Task)
                WHERE NOT (root)-[:SUBTASK_OF]->()
                RETURN [n IN nodes(path) | n] AS nodes
                ORDER BY length(path) DESC
                LIMIT 1
                """,
                tid=task_id,
            )
            record = await result.single()
            if not record:
                return []
            # Nodes come from leaf to root; reverse to get root→leaf order
            nodes = [TaskNode.from_neo4j_record(dict(n)) for n in record["nodes"]]
            nodes.reverse()
            return nodes

    async def get_children(self, task_id: str) -> list[TaskNode]:
        """Get direct children of a task."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (child:Task)-[:SUBTASK_OF]->(parent:Task {task_id: $tid})
                RETURN child
                ORDER BY child.priority, child.created_at
                """,
                tid=task_id,
            )
            records = await result.data()
            return [TaskNode.from_neo4j_record(dict(r["child"])) for r in records]

    async def get_subtree(self, task_id: str) -> dict:
        """Get the full subtree under a task as nested structure."""
        task = await self.get_task(task_id)
        if not task:
            return {}
        children = await self.get_children(task_id)
        child_trees = []
        for child in children:
            child_trees.append(await self.get_subtree(child.task_id))
        return {
            "task": task.model_dump(),
            "children": child_trees,
        }

    async def get_session_root_tasks(self, session_key: str) -> list[TaskNode]:
        """Get all root tasks (no SUBTASK_OF edge) for a session."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Task {session_key: $sk})
                WHERE NOT (t)-[:SUBTASK_OF]->()
                RETURN t
                ORDER BY t.created_at DESC
                """,
                sk=session_key,
            )
            records = await result.data()
            return [TaskNode.from_neo4j_record(dict(r["t"])) for r in records]

    async def get_focus_task(self, session_key: str) -> Optional[TaskNode]:
        """Find the current focus: deepest running/queued task in the session."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Task {session_key: $sk})
                WHERE t.state IN ['running', 'queued']
                RETURN t
                ORDER BY t.depth DESC, t.priority ASC, t.created_at ASC
                LIMIT 1
                """,
                sk=session_key,
            )
            record = await result.single()
            if not record:
                return None
            return TaskNode.from_neo4j_record(dict(record["t"]))

    async def check_siblings_all_completed(self, task_id: str) -> tuple[bool, Optional[str]]:
        """Check if all siblings of a task (under the same parent) are completed.
        Returns (all_completed, parent_id)."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Task {task_id: $tid})-[:SUBTASK_OF]->(parent:Task)
                OPTIONAL MATCH (sibling:Task)-[:SUBTASK_OF]->(parent)
                WITH parent,
                     collect(sibling.state) AS states
                RETURN parent.task_id AS parent_id,
                       all(s IN states WHERE s IN ['completed']) AS all_completed
                """,
                tid=task_id,
            )
            record = await result.single()
            if not record:
                return False, None
            return record["all_completed"], record["parent_id"]

    async def get_all_non_terminal_tasks(self) -> list[TaskNode]:
        """Get all tasks not in terminal state (for recovery)."""
        terminal = [s.value for s in TERMINAL_STATES]
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Task)
                WHERE NOT t.state IN $terminals
                RETURN t
                """,
                terminals=terminal,
            )
            records = await result.data()
            return [TaskNode.from_neo4j_record(dict(r["t"])) for r in records]

    async def get_session_task_counts(self, session_key: str) -> dict:
        """Get task count summary for a session."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Task {session_key: $sk})
                RETURN t.state AS state, count(t) AS cnt
                """,
                sk=session_key,
            )
            records = await result.data()
            counts = {r["state"]: r["cnt"] for r in records}
            total = sum(counts.values())
            return {
                "total": total,
                "completed": counts.get("completed", 0),
                "running": counts.get("running", 0),
                "failed": counts.get("failed", 0),
                "by_state": counts,
            }

    async def get_parent(self, task_id: str) -> Optional[TaskNode]:
        """Get the parent task of a given task."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Task {task_id: $tid})-[:SUBTASK_OF]->(parent:Task)
                RETURN parent
                """,
                tid=task_id,
            )
            record = await result.single()
            if not record:
                return None
            return TaskNode.from_neo4j_record(dict(record["parent"]))
