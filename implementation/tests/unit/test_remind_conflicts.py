"""Unit tests for remind + schedule conflict detection."""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

_CST = timezone(timedelta(hours=8))


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def schedule_with_hiking(tmp_path):
    """schedule.json with one event: 2026-03-22 10:00 爬山活动."""
    f = tmp_path / "schedule.json"
    f.write_text(json.dumps([
        {
            "id": "abc12345",
            "datetime": "2026-03-22 10:00",
            "title": "爬山活动",
            "note": "",
            "created_at": "2026-03-16 12:00",
        }
    ], ensure_ascii=False), encoding="utf-8")
    return f


@pytest.fixture
def empty_schedule(tmp_path):
    """Empty schedule.json."""
    f = tmp_path / "schedule.json"
    f.write_text("[]", encoding="utf-8")
    return f


# ── remind.py helper tests ───────────────────────────────────

def _get_remind_helpers(schedule_path):
    """Import remind module helpers with patched _SCHEDULE_FILE."""
    import importlib
    import tools.skills.notification.remind as remind_mod
    original = remind_mod._SCHEDULE_FILE
    remind_mod._SCHEDULE_FILE = schedule_path
    return remind_mod, original


def test_once_absolute_conflict_detected(schedule_with_hiking):
    """绝对时间与已有日程冲突 → 返回含警告。"""
    import tools.skills.notification.remind as remind_mod
    orig = remind_mod._SCHEDULE_FILE
    remind_mod._SCHEDULE_FILE = schedule_with_hiking
    try:
        target = datetime(2026, 3, 22, 10, 0, tzinfo=_CST)
        conflicts = remind_mod._check_conflicts(target, window_min=60)
        warning = remind_mod._conflict_warning(conflicts)
        assert len(conflicts) == 1
        assert "⚠️ 附近有日程安排" in warning
        assert "爬山活动" in warning
        assert "abc12345" in warning
    finally:
        remind_mod._SCHEDULE_FILE = orig


def test_once_absolute_no_conflict(schedule_with_hiking):
    """绝对时间无冲突 → 无警告。"""
    import tools.skills.notification.remind as remind_mod
    orig = remind_mod._SCHEDULE_FILE
    remind_mod._SCHEDULE_FILE = schedule_with_hiking
    try:
        target = datetime(2026, 3, 25, 14, 0, tzinfo=_CST)
        conflicts = remind_mod._check_conflicts(target, window_min=60)
        warning = remind_mod._conflict_warning(conflicts)
        assert conflicts == []
        assert warning == ""
    finally:
        remind_mod._SCHEDULE_FILE = orig


def test_once_relative_conflict_detected(schedule_with_hiking):
    """相对时间计算出的 fire_at 与已有日程冲突 → 冲突检测正常。"""
    import tools.skills.notification.remind as remind_mod
    orig = remind_mod._SCHEDULE_FILE
    remind_mod._SCHEDULE_FILE = schedule_with_hiking
    try:
        # fire_at = 2026-03-22 10:30, within ±60 min of 爬山活动 10:00
        fire_at = datetime(2026, 3, 22, 10, 30, tzinfo=_CST)
        conflicts = remind_mod._check_conflicts(fire_at, window_min=60)
        assert len(conflicts) == 1
        assert conflicts[0]["title"] == "爬山活动"
    finally:
        remind_mod._SCHEDULE_FILE = orig


def test_once_outside_window_no_conflict(schedule_with_hiking):
    """fire_at 超出 ±60 分钟窗口 → 无冲突。"""
    import tools.skills.notification.remind as remind_mod
    orig = remind_mod._SCHEDULE_FILE
    remind_mod._SCHEDULE_FILE = schedule_with_hiking
    try:
        # fire_at = 2026-03-22 12:01, > 60 min after 爬山活动 10:00
        fire_at = datetime(2026, 3, 22, 12, 1, tzinfo=_CST)
        conflicts = remind_mod._check_conflicts(fire_at, window_min=60)
        assert conflicts == []
    finally:
        remind_mod._SCHEDULE_FILE = orig


def test_cron_next_occurrence_conflict(schedule_with_hiking):
    """cron 下次触发时间与已有日程冲突 → 冲突检测正常。"""
    import tools.skills.notification.remind as remind_mod
    orig = remind_mod._SCHEDULE_FILE
    remind_mod._SCHEDULE_FILE = schedule_with_hiking
    try:
        # Simulate croniter next = 2026-03-22 10:00
        nxt = datetime(2026, 3, 22, 10, 0, tzinfo=_CST)
        conflicts = remind_mod._check_conflicts(nxt, window_min=60)
        warning = remind_mod._conflict_warning(conflicts)
        assert "⚠️ 附近有日程安排" in warning
        assert "爬山活动" in warning
    finally:
        remind_mod._SCHEDULE_FILE = orig


def test_empty_schedule_no_conflict(empty_schedule):
    """空日程 → 任何时间都无冲突。"""
    import tools.skills.notification.remind as remind_mod
    orig = remind_mod._SCHEDULE_FILE
    remind_mod._SCHEDULE_FILE = empty_schedule
    try:
        target = datetime(2026, 3, 22, 10, 0, tzinfo=_CST)
        conflicts = remind_mod._check_conflicts(target, window_min=60)
        assert conflicts == []
    finally:
        remind_mod._SCHEDULE_FILE = orig


# ── my_schedule.py helper tests ──────────────────────────────

def _get_schedule_helpers(data_file_path):
    """Import my_schedule module with patched _DATA_FILE."""
    import tools.skills.personal.my_schedule as sched_mod
    orig = sched_mod._DATA_FILE
    sched_mod._DATA_FILE = data_file_path
    return sched_mod, orig


def test_schedule_add_conflict(schedule_with_hiking):
    """schedule add 与已有日程冲突 → 含警告，操作成功。"""
    import tools.skills.personal.my_schedule as sched_mod
    orig = sched_mod._DATA_FILE
    sched_mod._DATA_FILE = schedule_with_hiking
    try:
        target = datetime(2026, 3, 22, 10, 15, tzinfo=_CST)
        conflicts = sched_mod._check_conflicts(target, exclude_id="new-id-xxx", window_min=30)
        warning = sched_mod._conflict_warning(conflicts)
        assert len(conflicts) == 1
        assert "⚠️ 附近有日程安排" in warning
        assert "爬山活动" in warning
    finally:
        sched_mod._DATA_FILE = orig


def test_schedule_add_no_conflict(schedule_with_hiking):
    """schedule add 无冲突 → 无警告。"""
    import tools.skills.personal.my_schedule as sched_mod
    orig = sched_mod._DATA_FILE
    sched_mod._DATA_FILE = schedule_with_hiking
    try:
        target = datetime(2026, 3, 22, 13, 0, tzinfo=_CST)
        conflicts = sched_mod._check_conflicts(target, exclude_id="new-id-xxx", window_min=30)
        assert conflicts == []
    finally:
        sched_mod._DATA_FILE = orig


def test_no_self_conflict(tmp_path):
    """schedule add 不与自身冲突（新事件 id 被排除）。"""
    import tools.skills.personal.my_schedule as sched_mod
    f = tmp_path / "schedule.json"
    new_id = "selftest1"
    f.write_text(json.dumps([
        {
            "id": new_id,
            "datetime": "2026-03-22 10:00",
            "title": "刚写入的事件",
            "note": "",
            "created_at": "2026-03-22 09:00",
        }
    ], ensure_ascii=False), encoding="utf-8")
    orig = sched_mod._DATA_FILE
    sched_mod._DATA_FILE = f
    try:
        target = datetime(2026, 3, 22, 10, 0, tzinfo=_CST)
        # exclude_id = new_id → no conflict with itself
        conflicts = sched_mod._check_conflicts(target, exclude_id=new_id, window_min=30)
        assert conflicts == []
    finally:
        sched_mod._DATA_FILE = orig


@pytest.mark.asyncio
async def test_schedule_add_returns_conflict_warning(tmp_path):
    """schedule add handler 直接返回含冲突警告的字符串。"""
    import tools.skills.personal.my_schedule as sched_mod
    f = tmp_path / "schedule.json"
    f.write_text(json.dumps([
        {
            "id": "exist001",
            "datetime": "2026-03-22 10:00",
            "title": "爬山活动",
            "note": "",
            "created_at": "2026-03-16 12:00",
        }
    ], ensure_ascii=False), encoding="utf-8")
    orig = sched_mod._DATA_FILE
    sched_mod._DATA_FILE = f
    try:
        ctx = MagicMock()
        result = await sched_mod.handle(
            {"action": "add", "datetime": "2026-03-22 10:15", "title": "集体合影"}, ctx
        )
        assert "已记录" in result
        assert "⚠️ 附近有日程安排" in result
        assert "爬山活动" in result
    finally:
        sched_mod._DATA_FILE = orig


@pytest.mark.asyncio
async def test_schedule_add_no_conflict_no_warning(empty_schedule):
    """schedule add 无冲突 → 返回不含 ⚠️。"""
    import tools.skills.personal.my_schedule as sched_mod
    orig = sched_mod._DATA_FILE
    sched_mod._DATA_FILE = empty_schedule
    try:
        ctx = MagicMock()
        result = await sched_mod.handle(
            {"action": "add", "datetime": "2026-03-25 14:00", "title": "喝水"}, ctx
        )
        assert "已记录" in result
        assert "⚠️" not in result
    finally:
        sched_mod._DATA_FILE = orig
