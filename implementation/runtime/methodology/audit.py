"""
Methodology audit logger — subscribes to methodology.* events
and persists them to daily JSONL files.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger("methodology-audit")

_CST = timezone(timedelta(hours=8))
_AUDIT_DIR = Path(__file__).resolve().parents[3] / "implementation" / "runtime" / "data" / "methodology" / "audit"

# Methodology event types
METHODOLOGY_EVENTS = {
    "methodology.feature_created",
    "methodology.phase_transition",
    "methodology.gate_passed",
    "methodology.gate_failed",
    "methodology.gate_skipped",
    "methodology.artifact_linked",
    "methodology.feature_completed",
}


def _audit_path() -> Path:
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(_CST).strftime("%Y-%m-%d")
    return _AUDIT_DIR / f"{date_str}.jsonl"


def write_audit_entry(
    event_type: str,
    feature_id: str,
    phase: str = "",
    gate_check: str = "",
    gate_result: str = "",
    details: dict = None,
) -> None:
    """Write a single audit entry to today's JSONL file."""
    entry = {
        "timestamp": datetime.now(_CST).isoformat(),
        "event_type": event_type,
        "feature_id": feature_id,
        "phase": phase,
        "gate_check": gate_check,
        "gate_result": gate_result,
        "details": details or {},
    }
    try:
        path = _audit_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Audit write failed: %s", e)


class MethodologyAuditLogger:
    """
    EventBus subscriber that listens to methodology.* events
    and writes them to the audit log.
    """

    def __init__(self, event_bus=None):
        self._event_bus = event_bus
        self._subscribed = False

    def subscribe(self) -> None:
        """Subscribe to all methodology events on the event_bus."""
        if self._event_bus is None or self._subscribed:
            return
        try:
            for event_type in METHODOLOGY_EVENTS:
                self._event_bus.subscribe(event_type, self._handle_event)
            self._subscribed = True
            log.info("MethodologyAuditLogger subscribed to %d event types", len(METHODOLOGY_EVENTS))
        except Exception as e:
            log.warning("Failed to subscribe to methodology events: %s", e)

    async def _handle_event(self, event) -> None:
        """Handle a methodology event and write to audit log."""
        try:
            event_type = getattr(event, "event_type", "")
            payload = getattr(event, "payload", {}) or {}

            feature_id = payload.get("feature_id", "")
            phase = payload.get("phase", payload.get("phase_from", ""))
            gate_check = payload.get("gate_check", "")
            gate_result = "passed" if payload.get("passed") else ""

            # Build details from remaining payload fields
            details = {
                k: v for k, v in payload.items()
                if k not in ("feature_id", "phase", "gate_check", "passed")
            }

            write_audit_entry(
                event_type=event_type,
                feature_id=feature_id,
                phase=phase,
                gate_check=gate_check,
                gate_result=gate_result,
                details=details,
            )
        except Exception as e:
            log.warning("Audit event handler error: %s", e)


def read_audit_log(date: Optional[str] = None, limit: int = 100) -> list[dict]:
    """Read audit entries for a given date (defaults to today)."""
    if date is None:
        date = datetime.now(_CST).strftime("%Y-%m-%d")
    path = _AUDIT_DIR / f"{date}.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        entries.reverse()  # newest first
        return entries[:limit]
    except Exception as e:
        log.warning("Failed to read audit log: %s", e)
        return []
