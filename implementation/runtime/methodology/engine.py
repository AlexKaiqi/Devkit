"""
MethodologyEngine — Feature state machine with gate enforcement.
Wraps graph_ops + ontology + gate_checker into a high-level interface.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any

from methodology.models import (
    Feature,
    ChangeType,
    Phase,
    GateType,
    GateResult,
    InterceptResult,
    Complexity,
    HaltCondition,
)
from methodology.ontology import get_ontology
from methodology.gate_checker import check_transition_gates

log = logging.getLogger("methodology-engine")

_CST = timezone(timedelta(hours=8))
_DEVKIT_ROOT = Path(__file__).resolve().parents[3]


def _now_iso() -> str:
    return datetime.now(_CST).isoformat()


class MethodologyEngine:
    """
    High-level Feature lifecycle manager.

    Degraded mode: if graph_store is None or Neo4j unavailable,
    features are stored in memory only (no cross-session persistence).
    """

    def __init__(self, graph_store=None, event_bus=None):
        """
        Args:
            graph_store: GraphStore instance (from task_graph). Used only for
                         passing the driver to MethodologyGraphOps. Can be None.
            event_bus: Optional EventBus for publishing methodology events.
        """
        self._graph_store = graph_store
        self._event_bus = event_bus
        self._graph_ops = None
        self._features: dict[str, Feature] = {}  # in-memory fallback
        self._feature_paths: dict[str, list[Phase]] = {}  # per-feature phase overrides
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize graph ops, create indexes if Neo4j available."""
        try:
            from methodology.graph_ops import MethodologyGraphOps
            driver = getattr(self._graph_store, "_driver", None)
            self._graph_ops = MethodologyGraphOps(driver=driver)
            if driver:
                await self._graph_ops.ensure_indexes()
                log.info("MethodologyEngine initialized with Neo4j")
            else:
                log.info("MethodologyEngine initialized in degraded (no Neo4j) mode")
        except Exception as e:
            log.warning("MethodologyEngine graph ops init failed: %s", e)
            from methodology.graph_ops import MethodologyGraphOps
            self._graph_ops = MethodologyGraphOps(driver=None)
        self._initialized = True

    async def _publish(self, event_type: str, feature_id: str, **extra) -> None:
        """Publish a methodology event if event_bus is available."""
        if self._event_bus:
            try:
                from event_bus import Event
                await self._event_bus.publish(Event(
                    event_type=event_type,
                    session_key=extra.get("session_key", ""),
                    payload={"feature_id": feature_id, **extra},
                ))
            except Exception as e:
                log.warning("Failed to publish event %s: %s", event_type, e)

    # ── Feature CRUD ──────────────────────────────────────

    async def create_feature(
        self,
        title: str,
        change_type: ChangeType,
        session_key: str = "",
        complexity: Complexity = Complexity.standard,
    ) -> Feature:
        """Create a new Feature in classify phase."""
        feature = Feature(
            feature_id=str(uuid.uuid4())[:8],
            title=title,
            change_type=change_type,
            current_phase=Phase.classify,
            status="active",
            session_key=session_key,
            created_at=_now_iso(),
            updated_at=_now_iso(),
            complexity=complexity,
        )
        # Inject decomposition phase for complex features if applicable
        self._inject_decomposition_phase(feature)
        # Store in memory
        self._features[feature.feature_id] = feature
        # Persist to Neo4j if available
        if self._graph_ops:
            try:
                await self._graph_ops.create_feature(feature)
            except Exception as e:
                log.warning("Failed to persist feature to Neo4j: %s", e)

        await self._publish(
            "methodology.feature_created",
            feature.feature_id,
            title=title,
            change_type=change_type.value,
            session_key=session_key,
        )
        log.info("Created Feature %s: %s (%s)", feature.feature_id, title, change_type.value)
        return feature

    async def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get Feature by ID — memory first, then Neo4j."""
        if feature_id in self._features:
            return self._features[feature_id]
        if self._graph_ops:
            try:
                feature = await self._graph_ops.get_feature(feature_id)
                if feature:
                    self._features[feature_id] = feature
                return feature
            except Exception as e:
                log.warning("Failed to get feature from Neo4j: %s", e)
        return None

    async def get_session_features(self, session_key: str) -> list[Feature]:
        """Get all active features for a session."""
        # Collect from memory
        mem_features = [
            f for f in self._features.values()
            if f.session_key == session_key and f.status == "active"
        ]
        # Merge with Neo4j (de-duplicate by feature_id)
        if self._graph_ops:
            try:
                neo4j_features = await self._graph_ops.list_active_features(session_key)
                mem_ids = {f.feature_id for f in mem_features}
                for f in neo4j_features:
                    if f.feature_id not in mem_ids:
                        mem_features.append(f)
                        self._features[f.feature_id] = f
            except Exception as e:
                log.warning("Failed to get session features from Neo4j: %s", e)
        return mem_features

    async def list_all_active_features(self) -> list[Feature]:
        """List all active features across all sessions."""
        # From memory
        mem_features = [f for f in self._features.values() if f.status == "active"]
        # From Neo4j
        if self._graph_ops:
            try:
                neo4j_features = await self._graph_ops.list_active_features()
                mem_ids = {f.feature_id for f in mem_features}
                for f in neo4j_features:
                    if f.feature_id not in mem_ids:
                        mem_features.append(f)
                        self._features[f.feature_id] = f
            except Exception as e:
                log.warning("Failed to list features from Neo4j: %s", e)
        return mem_features

    # ── State Machine ─────────────────────────────────────

    async def check_current_gates(self, feature_id: str) -> list[GateResult]:
        """
        Check gates for the transition from current_phase to next_phase.
        Returns list of GateResult; empty list if no gates or no next phase.
        """
        feature = await self.get_feature(feature_id)
        if not feature:
            return []

        ontology = get_ontology()
        next_phase = self._get_next_phase(feature)
        if not next_phase:
            return []

        results = check_transition_gates(
            feature.change_type,
            feature.current_phase,
            next_phase,
            feature_id,  # use feature_id as slug
            devkit_root=_DEVKIT_ROOT,
        )
        return results

    async def advance_phase(self, feature_id: str) -> list[GateResult]:
        """
        Attempt to advance Feature to next phase.
        - Runs all gate checks for current→next transition.
        - If any hard_block fails, returns the failed results without advancing.
        - If all hard_blocks pass (soft_warn failures are OK), advances the phase.

        Returns list of GateResult (all checks performed).
        """
        feature = await self.get_feature(feature_id)
        if not feature:
            return [GateResult(
                gate_check="feature_exists",
                passed=False,
                gate_type=GateType.hard_block,
                message=f"Feature {feature_id} not found",
            )]

        if feature.status != "active":
            return [GateResult(
                gate_check="feature_active",
                passed=False,
                gate_type=GateType.hard_block,
                message=f"Feature {feature_id} is not active (status={feature.status})",
            )]

        ontology = get_ontology()
        next_phase = self._get_next_phase(feature)
        if not next_phase:
            return [GateResult(
                gate_check="has_next_phase",
                passed=False,
                gate_type=GateType.soft_warn,
                message=f"Feature is already in the final phase ({feature.current_phase.value})",
            )]

        # Run gate checks
        results = check_transition_gates(
            feature.change_type,
            feature.current_phase,
            next_phase,
            feature_id,
            devkit_root=_DEVKIT_ROOT,
        )

        # Record each gate result in Neo4j
        if self._graph_ops:
            for r in results:
                try:
                    await self._graph_ops.record_gate_result(
                        feature_id=feature_id,
                        gate_check=r.gate_check,
                        phase_from=feature.current_phase.value,
                        phase_to=next_phase.value,
                        passed=r.passed,
                    )
                except Exception as e:
                    log.warning("Failed to record gate result: %s", e)

        # Check for hard block failures
        hard_failures = [r for r in results if not r.passed and r.gate_type == GateType.hard_block]
        if hard_failures:
            await self._publish(
                "methodology.gate_failed",
                feature_id,
                phase_from=feature.current_phase.value,
                phase_to=next_phase.value,
                failed_checks=[r.gate_check for r in hard_failures],
            )
            return results  # blocked, don't advance

        # All hard blocks passed — advance phase
        old_phase = feature.current_phase
        feature.current_phase = next_phase
        feature.updated_at = _now_iso()
        self._features[feature_id] = feature

        if self._graph_ops:
            try:
                await self._graph_ops.update_feature(
                    feature_id,
                    current_phase=next_phase,
                )
            except Exception as e:
                log.warning("Failed to update feature phase in Neo4j: %s", e)

        await self._publish(
            "methodology.phase_transition",
            feature_id,
            phase_from=old_phase.value,
            phase_to=next_phase.value,
        )
        log.info(
            "Feature %s advanced: %s → %s",
            feature_id, old_phase.value, next_phase.value,
        )
        return results

    async def skip_phase(
        self,
        feature_id: str,
        phase: Phase,
        reason: str,
    ) -> Optional[Feature]:
        """
        Record a skip reason for a phase and advance past it.
        Used when a phase is not applicable (e.g., skip requirements for a bug_fix).
        """
        feature = await self.get_feature(feature_id)
        if not feature:
            return None

        feature.skip_reasons[phase.value] = reason
        feature.updated_at = _now_iso()
        # If the feature is currently at this phase, advance it
        if feature.current_phase == phase:
            ontology = get_ontology()
            next_phase = ontology.get_next_phase(feature.change_type, phase)
            if next_phase:
                feature.current_phase = next_phase

        self._features[feature_id] = feature

        if self._graph_ops:
            try:
                await self._graph_ops.update_feature(
                    feature_id,
                    skip_reasons=str(feature.skip_reasons),
                    current_phase=feature.current_phase,
                )
            except Exception as e:
                log.warning("Failed to update skip reason in Neo4j: %s", e)

        await self._publish(
            "methodology.gate_skipped",
            feature_id,
            phase=phase.value,
            reason=reason,
        )
        log.info("Feature %s skipped phase %s: %s", feature_id, phase.value, reason)
        return feature

    async def complete_feature(self, feature_id: str) -> Optional[Feature]:
        """Mark a Feature as completed."""
        feature = await self.get_feature(feature_id)
        if not feature:
            return None

        feature.status = "completed"
        feature.updated_at = _now_iso()
        self._features[feature_id] = feature

        if self._graph_ops:
            try:
                await self._graph_ops.update_feature(feature_id, status="completed")
            except Exception as e:
                log.warning("Failed to complete feature in Neo4j: %s", e)

        await self._publish("methodology.feature_completed", feature_id)
        log.info("Feature %s completed", feature_id)
        return feature

    async def abandon_feature(self, feature_id: str, reason: str = "") -> Optional[Feature]:
        """Mark a Feature as abandoned."""
        feature = await self.get_feature(feature_id)
        if not feature:
            return None

        feature.status = "abandoned"
        feature.updated_at = _now_iso()
        self._features[feature_id] = feature

        if self._graph_ops:
            try:
                await self._graph_ops.update_feature(feature_id, status="abandoned")
            except Exception as e:
                log.warning("Failed to abandon feature in Neo4j: %s", e)

        return feature

    # ── Helpers ────────────────────────────────────────────

    def _inject_decomposition_phase(self, feature: Feature) -> None:
        """
        For complex features, inject decomposition phase into per-feature path.
        Only applies to new_capability and behavior_change.
        """
        if feature.complexity != Complexity.complex:
            return
        if feature.change_type not in (ChangeType.new_capability, ChangeType.behavior_change):
            return
        ontology = get_ontology()
        path = ontology.get_mandatory_path(feature.change_type)
        if not path:
            return
        phases = list(path.phases)
        if Phase.decomposition in phases:
            # Already present in ontology path
            self._feature_paths[feature.feature_id] = phases
            return
        # Inject after design
        if Phase.design in phases:
            idx = phases.index(Phase.design)
            phases.insert(idx + 1, Phase.decomposition)
        self._feature_paths[feature.feature_id] = phases
        log.info(
            "Injected decomposition phase for complex feature %s",
            feature.feature_id,
        )

    def _get_next_phase(self, feature: Feature) -> Optional[Phase]:
        """
        Get next phase for a feature, respecting per-feature path overrides.
        """
        # Check per-feature path first
        if feature.feature_id in self._feature_paths:
            phases = self._feature_paths[feature.feature_id]
            try:
                idx = phases.index(feature.current_phase)
            except ValueError:
                return None
            if idx + 1 >= len(phases):
                return None
            return phases[idx + 1]
        # Fall back to ontology
        ontology = get_ontology()
        return ontology.get_next_phase(feature.change_type, feature.current_phase)

    async def report_halt(
        self,
        feature_id: str,
        description: str,
        notes: str = "",
    ) -> Optional[HaltCondition]:
        """
        Record a halt condition on a feature (blocks further progress).
        Returns the created HaltCondition or None if feature not found.
        """
        feature = await self.get_feature(feature_id)
        if not feature:
            return None
        halt = HaltCondition(
            condition_id=str(uuid.uuid4())[:8],
            feature_id=feature_id,
            description=description,
            phase=feature.current_phase,
            resolved=False,
            created_at=_now_iso(),
            notes=notes,
        )
        feature.halt_conditions.append(halt)
        feature.updated_at = _now_iso()
        self._features[feature_id] = feature
        await self._publish(
            "methodology.halt_reported",
            feature_id,
            condition_id=halt.condition_id,
            description=description,
        )
        log.info("Halt condition %s reported for feature %s", halt.condition_id, feature_id)
        return halt

    async def resolve_halt(
        self,
        feature_id: str,
        condition_id: str,
        notes: str = "",
    ) -> bool:
        """
        Resolve a halt condition by condition_id.
        Returns True if found and resolved, False otherwise.
        """
        feature = await self.get_feature(feature_id)
        if not feature:
            return False
        for halt in feature.halt_conditions:
            if halt.condition_id == condition_id:
                halt.resolved = True
                halt.resolved_at = _now_iso()
                if notes:
                    halt.notes = notes
                feature.updated_at = _now_iso()
                self._features[feature_id] = feature
                await self._publish(
                    "methodology.halt_resolved",
                    feature_id,
                    condition_id=condition_id,
                )
                log.info("Halt condition %s resolved for feature %s", condition_id, feature_id)
                return True
        return False

    async def get_testing_strategy(self, feature_id: str) -> Optional[dict]:
        """
        Return the testing strategy for a feature based on its change_type.
        """
        feature = await self.get_feature(feature_id)
        if not feature:
            return None
        ontology = get_ontology()
        return ontology.get_testing_strategy(feature.change_type.value)

    # ── Artifact Linking ──────────────────────────────────

    async def link_artifact(
        self,
        feature_id: str,
        artifact_type: str,
        file_path: str,
        title: str = "",
    ) -> bool:
        """
        Link an artifact (acceptance_case, design_decision) to a Feature.
        Returns True on success.
        """
        feature = await self.get_feature(feature_id)
        if not feature:
            return False

        artifact_id = str(uuid.uuid4())[:8]
        if not title:
            title = Path(file_path).stem

        if self._graph_ops:
            try:
                if artifact_type == "acceptance_case":
                    await self._graph_ops.link_acceptance_case(
                        feature_id, artifact_id, title, file_path
                    )
                elif artifact_type == "design_decision":
                    await self._graph_ops.link_design_decision(
                        feature_id, artifact_id, title, file_path
                    )
                else:
                    log.warning("Unknown artifact type: %s", artifact_type)
                    return False
            except Exception as e:
                log.warning("Failed to link artifact: %s", e)
                return False

        await self._publish(
            "methodology.artifact_linked",
            feature_id,
            artifact_type=artifact_type,
            file_path=file_path,
        )
        return True

    async def scan_and_sync(self, feature_id: str) -> dict:
        """
        Scan the filesystem for artifacts matching this feature_id as slug,
        auto-link any found acceptance cases or design decisions.
        Returns summary of found artifacts.
        """
        import glob as glob_mod
        feature = await self.get_feature(feature_id)
        if not feature:
            return {"error": "Feature not found"}

        found = {"acceptance_cases": [], "design_decisions": []}

        # Scan acceptance cases
        pattern = str(_DEVKIT_ROOT / f"requirements/acceptance/**/*{feature_id}*.json")
        for f in glob_mod.glob(pattern, recursive=True):
            rel = str(Path(f).relative_to(_DEVKIT_ROOT))
            await self.link_artifact(feature_id, "acceptance_case", rel)
            found["acceptance_cases"].append(rel)

        # Scan design decisions
        for pattern_suffix in [
            f"design/decisions/*{feature_id}*.md",
            f"design/architecture/*{feature_id}*.md",
        ]:
            for f in glob_mod.glob(str(_DEVKIT_ROOT / pattern_suffix)):
                rel = str(Path(f).relative_to(_DEVKIT_ROOT))
                await self.link_artifact(feature_id, "design_decision", rel)
                found["design_decisions"].append(rel)

        return found

    async def get_feature_summary(self, feature_id: str) -> dict:
        """Get a summary of a Feature with gate status for display."""
        feature = await self.get_feature(feature_id)
        if not feature:
            return {}

        ontology = get_ontology()
        path = ontology.get_mandatory_path(feature.change_type)
        phases_summary = []

        if path:
            phases = path.phases
            current_idx = phases.index(feature.current_phase) if feature.current_phase in phases else -1

            for i, phase in enumerate(phases):
                if i < current_idx:
                    phase_status = "completed"
                elif i == current_idx:
                    phase_status = "current"
                else:
                    phase_status = "pending"

                phase_entry = {
                    "phase": phase.value,
                    "status": phase_status,
                    "skip_reason": feature.skip_reasons.get(phase.value, ""),
                }

                # Add gate results for current→next transition
                if phase_status == "current" and i + 1 < len(phases):
                    next_p = phases[i + 1]
                    gate_defs = ontology.get_gates(feature.change_type, phase, next_p)
                    if gate_defs:
                        gate_results = check_transition_gates(
                            feature.change_type, phase, next_p,
                            feature_id, _DEVKIT_ROOT,
                        )
                        phase_entry["gates"] = [
                            {
                                "check": r.gate_check,
                                "passed": r.passed,
                                "type": r.gate_type.value,
                                "message": r.message,
                                "template": r.template_path,
                            }
                            for r in gate_results
                        ]

                phases_summary.append(phase_entry)

        return {
            "feature_id": feature.feature_id,
            "title": feature.title,
            "change_type": feature.change_type.value,
            "current_phase": feature.current_phase.value,
            "status": feature.status,
            "session_key": feature.session_key,
            "phases": phases_summary,
        }
