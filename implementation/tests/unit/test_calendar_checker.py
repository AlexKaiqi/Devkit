"""Unit tests for CalendarChecker (feature: calendar-aware reminders)."""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from calendar_checker import (
    CalendarChecker,
    _matches_today,
    next_solar_date_for_lunar,
    next_solar_date_for_holiday,
    BUILTIN_HOLIDAYS,
)


# ── Helpers ─────────────────────────────────────────────────

def _entry(etype: str, **kwargs) -> dict:
    base = {
        "id": "test-id",
        "type": etype,
        "advance_days": 0,
        "time": "00:00",  # always "past" to avoid time-of-day gating in tests
        "message": "test message",
        "session_key": "s1",
        "last_notified_date": None,
    }
    base.update(kwargs)
    return base


# ── Test: holiday matches correct date ──────────────────────

def test_holiday_matches_correct_date():
    """中秋节（农历8/15）在正确公历日当天命中（advance_days=0）。"""
    # Compute the actual solar date for 中秋节 this/next year
    target = next_solar_date_for_holiday("中秋节")
    if target is None:
        pytest.skip("lunardate not installed or 中秋节 conversion failed")

    entry = _entry("holiday", name="中秋节", advance_days=0, time="00:00")
    assert _matches_today(entry, target) is True


def test_holiday_does_not_match_wrong_date():
    """在非节日公历日不命中。"""
    target = next_solar_date_for_holiday("中秋节")
    if target is None:
        pytest.skip("lunardate not installed")

    from datetime import timedelta
    wrong_date = target + timedelta(days=1)  # day after mid-autumn
    entry = _entry("holiday", name="中秋节", advance_days=0, time="00:00")
    assert _matches_today(entry, wrong_date) is False


# ── Test: advance_days offset ────────────────────────────────

def test_advance_days_offset():
    """advance_days=1 时应在节日前一天命中，节日当天不命中。"""
    target = next_solar_date_for_holiday("中秋节")
    if target is None:
        pytest.skip("lunardate not installed")

    from datetime import timedelta
    remind_date = target - timedelta(days=1)
    entry = _entry("holiday", name="中秋节", advance_days=1, time="00:00")

    assert _matches_today(entry, remind_date) is True
    assert _matches_today(entry, target) is False  # 节日当天不应命中


# ── Test: no double fire ─────────────────────────────────────

@pytest.mark.asyncio
async def test_no_double_fire(tmp_path):
    """last_notified_date=today 时不重复通知。"""
    today = date.today()
    target = next_solar_date_for_holiday("春节")
    if target is None:
        pytest.skip("lunardate not installed")

    entry = {
        "id": "no-double",
        "type": "holiday",
        "name": "春节",
        "advance_days": 0,
        "time": "00:00",
        "message": "新年快乐",
        "session_key": "s1",
        "last_notified_date": today.isoformat(),  # already notified today
    }
    data_path = tmp_path / "cal.json"
    data_path.write_text(json.dumps([entry]), encoding="utf-8")

    called = []

    async def fake_run_tool(name, args, session_key=""):
        called.append(name)
        return "ok"

    checker = CalendarChecker(data_path=data_path, run_tool_fn=fake_run_tool, interval_sec=99999)
    await checker._check_all()

    assert "notify" not in called, "Should not fire notify when last_notified_date == today"


# ── Test: lunar_date matches ─────────────────────────────────

def test_lunar_date_matches():
    """农历3/8 在正确公历日命中。"""
    target = next_solar_date_for_lunar(3, 8)
    if target is None:
        pytest.skip("lunardate not installed or lunar 3/8 conversion failed")

    entry = _entry("lunar_date", lunar_month=3, lunar_day=8, advance_days=0, time="00:00")
    assert _matches_today(entry, target) is True


# ── Test: unknown holiday skipped ────────────────────────────

def test_unknown_holiday_skipped():
    """未知节日名不命中，也不崩溃。"""
    entry = _entry("holiday", name="不存在节日XXXX", advance_days=0, time="00:00")
    today = date.today()
    result = _matches_today(entry, today)
    assert result is False


# ── Test: notify called with message ─────────────────────────

@pytest.mark.asyncio
async def test_notify_called_with_message(tmp_path):
    """命中时 notify 被调用且 message 正确。"""
    target = next_solar_date_for_holiday("端午节")
    if target is None:
        pytest.skip("lunardate not installed")

    entry = {
        "id": "notify-test",
        "type": "holiday",
        "name": "端午节",
        "advance_days": 0,
        "time": "09:00",
        "message": "端午节快乐！记得买粽子",
        "session_key": "s1",
        "last_notified_date": None,
    }
    data_path = tmp_path / "cal.json"
    data_path.write_text(json.dumps([entry]), encoding="utf-8")

    notified = []

    async def fake_run_tool(name, args, session_key=""):
        if name == "notify":
            notified.append(args.get("message", ""))
        return "ok"

    from datetime import datetime, timezone, timedelta
    _CST = timezone(timedelta(hours=8))
    # 模拟触发时间在 09:00（窗口内）
    fake_now = datetime(target.year, target.month, target.day, 9, 5, tzinfo=_CST)

    checker = CalendarChecker(data_path=data_path, run_tool_fn=fake_run_tool, interval_sec=99999)
    # Simulate that today == target
    # We call _check_all with today forced to target via monkeypatching
    import calendar_checker as cc_module
    original_today = cc_module.date

    class FakeDate(date):
        @classmethod
        def today(cls):
            return target

    cc_module.date = FakeDate
    try:
        await checker._check_all(_now_cst=fake_now)
    finally:
        cc_module.date = original_today

    assert len(notified) == 1, f"Expected 1 notify call, got {len(notified)}"
    assert "端午节快乐" in notified[0], f"Message mismatch: {notified[0]}"

    # Verify last_notified_date was updated
    updated = json.loads(data_path.read_text())
    assert updated[0]["last_notified_date"] == target.isoformat()
