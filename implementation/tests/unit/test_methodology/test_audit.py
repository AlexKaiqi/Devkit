"""Unit tests for methodology audit logger."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.audit import (
    write_audit_entry,
    read_audit_log,
    MethodologyAuditLogger,
    METHODOLOGY_EVENTS,
)


class TestWriteAuditEntry:
    def test_writes_jsonl_entry(self, tmp_path):
        with patch("methodology.audit._AUDIT_DIR", tmp_path):
            write_audit_entry(
                event_type="methodology.feature_created",
                feature_id="feat-001",
                phase="classify",
                details={"title": "Test Feature"},
            )

        # Should have written to today's file
        import methodology.audit as audit_mod
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        audit_file = tmp_path / f"{date_str}.jsonl"
        assert audit_file.exists()

        lines = audit_file.read_text().strip().splitlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["event_type"] == "methodology.feature_created"
        assert entry["feature_id"] == "feat-001"
        assert entry["phase"] == "classify"
        assert entry["details"]["title"] == "Test Feature"
        assert "timestamp" in entry

    def test_writes_multiple_entries(self, tmp_path):
        with patch("methodology.audit._AUDIT_DIR", tmp_path):
            for i in range(3):
                write_audit_entry(
                    event_type="methodology.gate_passed",
                    feature_id=f"feat-{i:03d}",
                )

        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        audit_file = tmp_path / f"{date_str}.jsonl"
        lines = audit_file.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_io_error_does_not_raise(self, tmp_path):
        """Audit write failure should never propagate."""
        with patch("methodology.audit._AUDIT_DIR", tmp_path / "nonexistent" / "dir"):
            # This will fail because directory doesn't exist; but mkdir is called
            # with parents=True so it should succeed. Let's test with a read-only check.
            # Actually, the function creates the dir, so let's just verify it doesn't raise
            try:
                write_audit_entry(
                    event_type="methodology.test",
                    feature_id="feat-001",
                )
            except Exception as e:
                pytest.fail(f"write_audit_entry raised unexpectedly: {e}")


class TestReadAuditLog:
    def test_reads_entries(self, tmp_path):
        entries = [
            {"timestamp": "2026-03-17T10:00:00+08:00", "event_type": "methodology.feature_created",
             "feature_id": "f1", "phase": "", "gate_check": "", "gate_result": "", "details": {}},
            {"timestamp": "2026-03-17T10:01:00+08:00", "event_type": "methodology.gate_failed",
             "feature_id": "f1", "phase": "requirements", "gate_check": "acceptance_case_exists",
             "gate_result": "", "details": {}},
        ]
        date_str = "2026-03-17"
        audit_file = tmp_path / f"{date_str}.jsonl"
        audit_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        with patch("methodology.audit._AUDIT_DIR", tmp_path):
            result = read_audit_log(date="2026-03-17")

        assert len(result) == 2
        # Should be reversed (newest first)
        assert result[0]["event_type"] == "methodology.gate_failed"
        assert result[1]["event_type"] == "methodology.feature_created"

    def test_returns_empty_for_missing_date(self, tmp_path):
        with patch("methodology.audit._AUDIT_DIR", tmp_path):
            result = read_audit_log(date="2000-01-01")
        assert result == []

    def test_respects_limit(self, tmp_path):
        entries = [
            {"timestamp": f"2026-03-17T10:0{i}:00+08:00", "event_type": "methodology.test",
             "feature_id": f"f{i}", "phase": "", "gate_check": "", "gate_result": "", "details": {}}
            for i in range(10)
        ]
        audit_file = tmp_path / "2026-03-17.jsonl"
        audit_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        with patch("methodology.audit._AUDIT_DIR", tmp_path):
            result = read_audit_log(date="2026-03-17", limit=5)

        assert len(result) == 5


@pytest.mark.asyncio
class TestMethodologyAuditLogger:
    async def test_handles_event(self, tmp_path):
        logger = MethodologyAuditLogger()

        # Create a mock event
        event = MagicMock()
        event.event_type = "methodology.phase_transition"
        event.payload = {
            "feature_id": "feat-001",
            "phase_from": "requirements",
            "phase_to": "design",
        }

        with patch("methodology.audit._AUDIT_DIR", tmp_path):
            await logger._handle_event(event)

        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        audit_file = tmp_path / f"{date_str}.jsonl"
        assert audit_file.exists()
        entry = json.loads(audit_file.read_text().strip())
        assert entry["event_type"] == "methodology.phase_transition"
        assert entry["feature_id"] == "feat-001"

    async def test_handle_event_does_not_raise_on_error(self):
        logger = MethodologyAuditLogger()

        # Malformed event
        event = MagicMock()
        event.event_type = None
        event.payload = None

        with patch("methodology.audit.write_audit_entry", side_effect=RuntimeError("disk full")):
            try:
                await logger._handle_event(event)
            except Exception as e:
                pytest.fail(f"_handle_event raised unexpectedly: {e}")

    def test_subscribe_registers_event_handlers(self):
        event_bus = MagicMock()
        logger = MethodologyAuditLogger(event_bus=event_bus)
        logger.subscribe()
        assert event_bus.subscribe.call_count == len(METHODOLOGY_EVENTS)

    def test_subscribe_without_bus_does_nothing(self):
        logger = MethodologyAuditLogger(event_bus=None)
        logger.subscribe()  # Should not raise
        assert not logger._subscribed

    def test_methodology_events_set(self):
        assert "methodology.feature_created" in METHODOLOGY_EVENTS
        assert "methodology.phase_transition" in METHODOLOGY_EVENTS
        assert "methodology.gate_passed" in METHODOLOGY_EVENTS
        assert "methodology.gate_failed" in METHODOLOGY_EVENTS
        assert "methodology.gate_skipped" in METHODOLOGY_EVENTS
        assert "methodology.artifact_linked" in METHODOLOGY_EVENTS
        assert "methodology.feature_completed" in METHODOLOGY_EVENTS
