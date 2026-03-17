"""
Neo4j graph operations for Methodology Feature lifecycle.
Reuses the same Neo4j connection pattern as task_graph/graph_store.py.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from methodology.models import Feature, ChangeType, Phase

log = logging.getLogger("methodology-graph-ops")

_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).isoformat()


class MethodologyGraphOps:
    """Neo4j operations for Feature nodes and related artifacts."""

    def __init__(self, driver):
        """
        Args:
            driver: An async Neo4j driver (AsyncDriver from neo4j package).
                    If None, all operations are no-ops (degraded mode).
        """
        self._driver = driver

    # ── Feature CRUD ──────────────────────────────────────

    async def create_feature(self, feature: Feature) -> Feature:
        """Create a Feature node in Neo4j."""
        if self._driver is None:
            return feature
        props = {
            "feature_id": feature.feature_id,
            "title": feature.title,
            "change_type": feature.change_type.value,
            "current_phase": feature.current_phase.value,
            "status": feature.status,
            "session_key": feature.session_key,
            "skip_reasons": str(feature.skip_reasons),
            "created_at": feature.created_at or _now_iso(),
            "updated_at": feature.updated_at or _now_iso(),
        }
        async with self._driver.session() as session:
            await session.run("CREATE (f:Feature $props)", props=props)
        log.info("Created Feature %s: %s", feature.feature_id[:8], feature.title)
        return feature

    async def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Fetch a Feature by ID."""
        if self._driver is None:
            return None
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (f:Feature {feature_id: $fid}) RETURN f",
                fid=feature_id,
            )
            record = await result.single()
            if not record:
                return None
            return _record_to_feature(dict(record["f"]))

    async def update_feature(self, feature_id: str, **updates) -> Optional[Feature]:
        """Update Feature properties. Returns the updated Feature."""
        if self._driver is None:
            return None
        updates["updated_at"] = _now_iso()
        # Convert enum values to strings
        for k, v in list(updates.items()):
            if hasattr(v, "value"):
                updates[k] = v.value
        set_clauses = ", ".join(f"f.{k} = ${k}" for k in updates)
        async with self._driver.session() as session:
            result = await session.run(
                f"MATCH (f:Feature {{feature_id: $fid}}) SET {set_clauses} RETURN f",
                fid=feature_id,
                **updates,
            )
            record = await result.single()
            if not record:
                return None
            return _record_to_feature(dict(record["f"]))

    async def list_active_features(self, session_key: str = "") -> list[Feature]:
        """List active features, optionally filtered by session."""
        if self._driver is None:
            return []
        async with self._driver.session() as session:
            if session_key:
                result = await session.run(
                    "MATCH (f:Feature {status: 'active', session_key: $sk}) RETURN f ORDER BY f.created_at DESC",
                    sk=session_key,
                )
            else:
                result = await session.run(
                    "MATCH (f:Feature {status: 'active'}) RETURN f ORDER BY f.created_at DESC"
                )
            records = await result.data()
            return [_record_to_feature(dict(r["f"])) for r in records]

    async def list_all_features(self, session_key: str = "") -> list[Feature]:
        """List all features (any status), optionally filtered by session."""
        if self._driver is None:
            return []
        async with self._driver.session() as session:
            if session_key:
                result = await session.run(
                    "MATCH (f:Feature {session_key: $sk}) RETURN f ORDER BY f.created_at DESC",
                    sk=session_key,
                )
            else:
                result = await session.run(
                    "MATCH (f:Feature) RETURN f ORDER BY f.created_at DESC"
                )
            records = await result.data()
            return [_record_to_feature(dict(r["f"])) for r in records]

    # ── Artifact Linking ──────────────────────────────────

    async def link_acceptance_case(
        self,
        feature_id: str,
        case_id: str,
        title: str,
        file_path: str,
    ) -> None:
        """Create AcceptanceCase node and link to Feature."""
        if self._driver is None:
            return
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (f:Feature {feature_id: $fid})
                MERGE (a:AcceptanceCase {case_id: $cid})
                SET a.title = $title, a.file_path = $file_path,
                    a.status = 'draft', a.created_at = $now
                MERGE (a)-[:BELONGS_TO]->(f)
                """,
                fid=feature_id,
                cid=case_id,
                title=title,
                file_path=file_path,
                now=_now_iso(),
            )

    async def link_design_decision(
        self,
        feature_id: str,
        decision_id: str,
        title: str,
        file_path: str,
    ) -> None:
        """Create DesignDecision node and link to Feature."""
        if self._driver is None:
            return
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (f:Feature {feature_id: $fid})
                MERGE (d:DesignDecision {decision_id: $did})
                SET d.title = $title, d.file_path = $file_path,
                    d.status = 'active', d.created_at = $now
                MERGE (d)-[:COVERS]->(f)
                """,
                fid=feature_id,
                did=decision_id,
                title=title,
                file_path=file_path,
                now=_now_iso(),
            )

    async def record_gate_result(
        self,
        feature_id: str,
        gate_check: str,
        phase_from: str,
        phase_to: str,
        passed: bool,
        skip_reason: str = "",
    ) -> None:
        """Record a GateResult node and link to Feature."""
        if self._driver is None:
            return
        gate_id = str(uuid.uuid4())[:8]
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (f:Feature {feature_id: $fid})
                CREATE (g:GateResult {
                    gate_id: $gid,
                    gate_check: $gate_check,
                    phase_from: $phase_from,
                    phase_to: $phase_to,
                    passed: $passed,
                    skip_reason: $skip_reason,
                    checked_at: $now
                })
                CREATE (g)-[:CHECKS]->(f)
                """,
                fid=feature_id,
                gid=gate_id,
                gate_check=gate_check,
                phase_from=phase_from,
                phase_to=phase_to,
                passed=passed,
                skip_reason=skip_reason,
                now=_now_iso(),
            )

    async def record_evidence(
        self,
        feature_id: str,
        evidence_type: str,
        summary: str,
        file_path: str = "",
    ) -> None:
        """Record an Evidence node and link to Feature."""
        if self._driver is None:
            return
        evidence_id = str(uuid.uuid4())[:8]
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (f:Feature {feature_id: $fid})
                CREATE (e:Evidence {
                    evidence_id: $eid,
                    type: $type,
                    summary: $summary,
                    file_path: $file_path,
                    collected_at: $now
                })
                CREATE (e)-[:EVIDENCES]->(f)
                """,
                fid=feature_id,
                eid=evidence_id,
                type=evidence_type,
                summary=summary,
                file_path=file_path,
                now=_now_iso(),
            )

    # ── Queries ───────────────────────────────────────────

    async def get_feature_with_artifacts(self, feature_id: str) -> dict:
        """Get Feature with all linked artifacts."""
        if self._driver is None:
            return {}
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (f:Feature {feature_id: $fid})
                OPTIONAL MATCH (a:AcceptanceCase)-[:BELONGS_TO]->(f)
                OPTIONAL MATCH (d:DesignDecision)-[:COVERS]->(f)
                OPTIONAL MATCH (e:Evidence)-[:EVIDENCES]->(f)
                RETURN f,
                       collect(DISTINCT a) AS acceptance_cases,
                       collect(DISTINCT d) AS design_decisions,
                       collect(DISTINCT e) AS evidence
                """,
                fid=feature_id,
            )
            record = await result.single()
            if not record:
                return {}
            feature = _record_to_feature(dict(record["f"]))
            return {
                "feature": feature.model_dump(),
                "acceptance_cases": [dict(a) for a in record["acceptance_cases"] if a],
                "design_decisions": [dict(d) for d in record["design_decisions"] if d],
                "evidence": [dict(e) for e in record["evidence"] if e],
            }

    async def get_features_by_session(self, session_key: str) -> list[Feature]:
        """Get all features for a session (any status)."""
        return await self.list_all_features(session_key=session_key)

    async def ensure_indexes(self) -> None:
        """Create Feature-related indexes if they don't exist."""
        if self._driver is None:
            return
        async with self._driver.session() as session:
            for cypher in [
                "CREATE CONSTRAINT feature_id_unique IF NOT EXISTS FOR (f:Feature) REQUIRE f.feature_id IS UNIQUE",
                "CREATE INDEX feature_session_idx IF NOT EXISTS FOR (f:Feature) ON (f.session_key)",
                "CREATE INDEX feature_status_idx IF NOT EXISTS FOR (f:Feature) ON (f.status)",
                "CREATE INDEX acceptance_case_id_idx IF NOT EXISTS FOR (a:AcceptanceCase) ON (a.case_id)",
                "CREATE INDEX design_decision_id_idx IF NOT EXISTS FOR (d:DesignDecision) ON (d.decision_id)",
            ]:
                try:
                    await session.run(cypher)
                except Exception as e:
                    log.warning("Index creation warning: %s", e)
        log.info("Feature graph indexes ensured")


def _record_to_feature(props: dict) -> Feature:
    """Convert a Neo4j record dict to a Feature model."""
    import ast
    skip_reasons_raw = props.get("skip_reasons", "{}")
    if isinstance(skip_reasons_raw, str):
        try:
            skip_reasons = ast.literal_eval(skip_reasons_raw)
            if not isinstance(skip_reasons, dict):
                skip_reasons = {}
        except Exception:
            skip_reasons = {}
    elif isinstance(skip_reasons_raw, dict):
        skip_reasons = skip_reasons_raw
    else:
        skip_reasons = {}

    return Feature(
        feature_id=props.get("feature_id", ""),
        title=props.get("title", ""),
        change_type=ChangeType(props.get("change_type", "new_capability")),
        current_phase=Phase(props.get("current_phase", "classify")),
        status=props.get("status", "active"),
        session_key=props.get("session_key", ""),
        skip_reasons=skip_reasons,
        created_at=props.get("created_at", ""),
        updated_at=props.get("updated_at", ""),
    )
