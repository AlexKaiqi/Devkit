"""Unit tests for MethodologyEngine state machine."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.models import (
    ChangeType, Phase, GateType, GateResult, Feature
)


def _make_feature(
    feature_id="test-001",
    change_type=ChangeType.new_capability,
    current_phase=Phase.classify,
    status="active",
    session_key="test-session",
) -> Feature:
    return Feature(
        feature_id=feature_id,
        title="Test Feature",
        change_type=change_type,
        current_phase=current_phase,
        status=status,
        session_key=session_key,
        created_at="2026-03-17T10:00:00+08:00",
        updated_at="2026-03-17T10:00:00+08:00",
    )


@pytest.fixture
def engine_no_neo4j():
    """Create MethodologyEngine without Neo4j (in-memory only)."""
    from methodology.engine import MethodologyEngine
    engine = MethodologyEngine(graph_store=None, event_bus=None)
    # Initialize synchronously for tests
    from methodology.graph_ops import MethodologyGraphOps
    engine._graph_ops = MethodologyGraphOps(driver=None)
    engine._initialized = True
    return engine


@pytest.mark.asyncio
class TestCreateFeature:
    async def test_creates_feature(self, engine_no_neo4j):
        engine = engine_no_neo4j
        feature = await engine.create_feature(
            title="新提醒功能",
            change_type=ChangeType.new_capability,
            session_key="test-session",
        )
        assert feature.title == "新提醒功能"
        assert feature.change_type == ChangeType.new_capability
        assert feature.current_phase == Phase.classify
        assert feature.status == "active"
        assert feature.session_key == "test-session"
        assert feature.feature_id  # non-empty

    async def test_feature_stored_in_memory(self, engine_no_neo4j):
        engine = engine_no_neo4j
        feature = await engine.create_feature(
            title="Test",
            change_type=ChangeType.bug_fix,
        )
        assert feature.feature_id in engine._features

    async def test_get_feature_returns_created(self, engine_no_neo4j):
        engine = engine_no_neo4j
        created = await engine.create_feature(
            title="Memory Test",
            change_type=ChangeType.refactoring,
        )
        fetched = await engine.get_feature(created.feature_id)
        assert fetched is not None
        assert fetched.feature_id == created.feature_id
        assert fetched.title == "Memory Test"


@pytest.mark.asyncio
class TestAdvancePhase:
    async def test_advance_fails_when_hard_block_missing(self, engine_no_neo4j, tmp_path):
        """new_capability: requirements→design requires acceptance_case_exists."""
        engine = engine_no_neo4j

        feature = await engine.create_feature(
            title="Test Capability",
            change_type=ChangeType.new_capability,
        )

        # Manually set to requirements phase
        feature.current_phase = Phase.requirements
        engine._features[feature.feature_id] = feature

        # Patch devkit root to tmp_path (no acceptance files there)
        with patch("methodology.engine._DEVKIT_ROOT", tmp_path):
            with patch("methodology.gate_checker._DEVKIT_ROOT", tmp_path):
                results = await engine.advance_phase(feature.feature_id)

        # Should have at least one failed hard_block result
        hard_failures = [r for r in results if not r.passed and r.gate_type == GateType.hard_block]
        assert len(hard_failures) > 0, f"Expected hard_block failure, got: {results}"

        # Feature should NOT have advanced
        updated = await engine.get_feature(feature.feature_id)
        assert updated.current_phase == Phase.requirements

    async def test_advance_succeeds_when_gate_passes(self, engine_no_neo4j, tmp_path):
        """new_capability: requirements→design gate passes when acceptance file exists."""
        engine = engine_no_neo4j

        feature_id = "test-abc"
        feature = _make_feature(feature_id=feature_id, current_phase=Phase.requirements)
        engine._features[feature_id] = feature

        # Create the expected acceptance case file
        acpt_dir = tmp_path / "requirements" / "acceptance"
        acpt_dir.mkdir(parents=True)
        (acpt_dir / f"test-{feature_id}-scenario.json").write_text("{}")

        with patch("methodology.engine._DEVKIT_ROOT", tmp_path):
            with patch("methodology.gate_checker._DEVKIT_ROOT", tmp_path):
                results = await engine.advance_phase(feature_id)

        # No hard failures
        hard_failures = [r for r in results if not r.passed and r.gate_type == GateType.hard_block]
        assert len(hard_failures) == 0, f"Unexpected hard failures: {hard_failures}"

        # Feature should have advanced to design
        updated = await engine.get_feature(feature_id)
        assert updated.current_phase == Phase.design

    async def test_advance_on_nonexistent_feature(self, engine_no_neo4j):
        results = await engine_no_neo4j.advance_phase("nonexistent-id")
        assert len(results) == 1
        assert results[0].passed is False
        assert "not found" in results[0].message.lower() or "找不到" in results[0].message.lower() or "Feature" in results[0].message

    async def test_advance_on_final_phase(self, engine_no_neo4j):
        engine = engine_no_neo4j
        feature_id = "final-feature"
        feature = _make_feature(feature_id=feature_id, current_phase=Phase.finalize)
        engine._features[feature_id] = feature

        results = await engine.advance_phase(feature_id)
        assert len(results) == 1
        # Should return soft_warn or hard_block about being at last phase
        assert results[0].passed is False


@pytest.mark.asyncio
class TestSkipPhase:
    async def test_skip_records_reason(self, engine_no_neo4j):
        engine = engine_no_neo4j
        feature = await engine.create_feature(
            title="Skip Test",
            change_type=ChangeType.new_capability,
        )
        # Manually put in requirements phase
        feature.current_phase = Phase.requirements
        engine._features[feature.feature_id] = feature

        updated = await engine.skip_phase(
            feature.feature_id,
            Phase.requirements,
            "沿用现有验收场景",
        )
        assert updated is not None
        assert updated.skip_reasons.get("requirements") == "沿用现有验收场景"

    async def test_skip_advances_phase(self, engine_no_neo4j):
        engine = engine_no_neo4j
        feature = await engine.create_feature(
            title="Skip Advance Test",
            change_type=ChangeType.new_capability,
        )
        feature.current_phase = Phase.requirements
        engine._features[feature.feature_id] = feature

        updated = await engine.skip_phase(
            feature.feature_id,
            Phase.requirements,
            "理由",
        )
        # Should advance to design
        assert updated.current_phase == Phase.design

    async def test_skip_returns_none_for_missing_feature(self, engine_no_neo4j):
        result = await engine_no_neo4j.skip_phase("missing", Phase.requirements, "reason")
        assert result is None


@pytest.mark.asyncio
class TestCompleteFeature:
    async def test_complete_sets_status(self, engine_no_neo4j):
        engine = engine_no_neo4j
        feature = await engine.create_feature(
            title="Complete Test",
            change_type=ChangeType.bug_fix,
        )
        result = await engine.complete_feature(feature.feature_id)
        assert result is not None
        assert result.status == "completed"

        # Verify in memory
        stored = await engine.get_feature(feature.feature_id)
        assert stored.status == "completed"


@pytest.mark.asyncio
class TestGetSessionFeatures:
    async def test_returns_session_features(self, engine_no_neo4j):
        engine = engine_no_neo4j
        f1 = await engine.create_feature("F1", ChangeType.new_capability, "session-A")
        f2 = await engine.create_feature("F2", ChangeType.bug_fix, "session-A")
        f3 = await engine.create_feature("F3", ChangeType.refactoring, "session-B")

        features_a = await engine.get_session_features("session-A")
        assert len(features_a) == 2
        ids = {f.feature_id for f in features_a}
        assert f1.feature_id in ids
        assert f2.feature_id in ids
        assert f3.feature_id not in ids

    async def test_excludes_completed_features(self, engine_no_neo4j):
        engine = engine_no_neo4j
        feature = await engine.create_feature("Completed", ChangeType.doc_revision, "session-C")
        await engine.complete_feature(feature.feature_id)

        active = await engine.get_session_features("session-C")
        assert not any(f.feature_id == feature.feature_id for f in active)


@pytest.mark.asyncio
class TestGetFeatureSummary:
    async def test_returns_summary(self, engine_no_neo4j, tmp_path):
        engine = engine_no_neo4j
        feature = await engine.create_feature(
            "Summary Test",
            ChangeType.new_capability,
        )

        with patch("methodology.engine._DEVKIT_ROOT", tmp_path):
            with patch("methodology.gate_checker._DEVKIT_ROOT", tmp_path):
                summary = await engine.get_feature_summary(feature.feature_id)

        assert summary["feature_id"] == feature.feature_id
        assert summary["title"] == "Summary Test"
        assert summary["change_type"] == "new_capability"
        assert "phases" in summary
        assert len(summary["phases"]) > 0

    async def test_returns_empty_for_missing(self, engine_no_neo4j):
        summary = await engine_no_neo4j.get_feature_summary("nonexistent")
        assert summary == {}
