"""Tests for remind/timer persistence in EventBus."""

import asyncio
import json
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))
from event_bus import EventBus


@pytest.fixture
def tmp_persist_path(tmp_path):
    return tmp_path / "timers.json"


@pytest.mark.asyncio
async def test_persist_file_written_on_schedule(tmp_persist_path):
    """schedule 后 timers.json 含该 timer_id"""
    bus = EventBus(persist_path=tmp_persist_path)
    timer_id = await bus.schedule_timer(60, "session-1", {"msg": "hello"})
    await bus.shutdown()

    assert tmp_persist_path.exists()
    data = json.loads(tmp_persist_path.read_text())
    ids = [entry["id"] for entry in data]
    assert timer_id in ids


@pytest.mark.asyncio
async def test_persist_file_updated_on_cancel(tmp_persist_path):
    """cancel 后 timer_id 从文件消失"""
    bus = EventBus(persist_path=tmp_persist_path)
    timer_id = await bus.schedule_timer(60, "session-1", {"msg": "hello"})

    # Verify it's written
    data = json.loads(tmp_persist_path.read_text())
    assert timer_id in [e["id"] for e in data]

    # Cancel
    task = bus._timers.get(timer_id)  # grab before cancel
    cancelled = bus.cancel_timer(timer_id)
    assert cancelled is True

    # Pump the event loop until the task is done (its finally block will call _persist)
    for _ in range(20):
        await asyncio.sleep(0.01)
        if task is None or task.done():
            break

    data = json.loads(tmp_persist_path.read_text())
    assert timer_id not in [e["id"] for e in data]
    await bus.shutdown()


@pytest.mark.asyncio
async def test_persist_file_cleaned_on_fire(tmp_persist_path):
    """timer 触发后条目从文件移除"""
    bus = EventBus(persist_path=tmp_persist_path)
    fired_events = []

    async def on_fire(event):
        fired_events.append(event)

    bus.subscribe("timer.fired", on_fire)

    timer_id = await bus.schedule_timer(0.05, "session-1", {"msg": "fire"})

    # Wait for timer to fire
    await asyncio.sleep(0.2)

    assert len(fired_events) == 1
    assert fired_events[0].payload["timer_id"] == timer_id

    data = json.loads(tmp_persist_path.read_text())
    assert timer_id not in [e["id"] for e in data]
    await bus.shutdown()


@pytest.mark.asyncio
async def test_restore_pending_timers(tmp_persist_path):
    """写入 timers.json → 新 EventBus restore → timer 仍然触发"""
    # Manually write a timer that fires in 0.1s
    fire_at = time.time() + 0.1
    entry = {
        "id": "test-restore-id",
        "session_key": "session-restore",
        "fire_at": fire_at,
        "payload": {"msg": "restored"},
    }
    tmp_persist_path.write_text(json.dumps([entry]))

    fired_events = []

    bus = EventBus(persist_path=tmp_persist_path)
    bus.subscribe("timer.fired", lambda e: fired_events.append(e) or asyncio.sleep(0))

    # Use a proper async handler
    async def on_fire(event):
        fired_events.append(event)

    bus.subscribe("timer.fired", on_fire)

    await bus.restore_timers()

    # Wait for timer to fire
    await asyncio.sleep(0.5)

    assert any(e.payload.get("timer_id") == "test-restore-id" for e in fired_events)
    await bus.shutdown()


@pytest.mark.asyncio
async def test_restore_ignores_expired(tmp_persist_path):
    """fire_at 在过去的条目不被 restore，不报错"""
    entry = {
        "id": "expired-id",
        "session_key": "session-x",
        "fire_at": time.time() - 100,  # in the past
        "payload": {},
    }
    tmp_persist_path.write_text(json.dumps([entry]))

    bus = EventBus(persist_path=tmp_persist_path)
    # Should not raise
    await bus.restore_timers()

    # The expired timer should not be in memory timers
    assert "expired-id" not in bus._timer_meta

    await bus.shutdown()
