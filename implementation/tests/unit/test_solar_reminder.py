"""Unit tests for solar_date (公历年度日期) reminder feature."""

import json
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

_CST = timezone(timedelta(hours=8))


# ═══════════════════════════════════════════════════════════════
# remind.py — _next_solar_for_solar
# ═══════════════════════════════════════════════════════════════

def test_next_solar_for_solar_this_year():
    """今年日期未过 → 返回今年。"""
    from tools.skills.notification.remind import _next_solar_for_solar
    today = date(2026, 1, 1)
    result = _next_solar_for_solar(2, 14, today)
    assert result == date(2026, 2, 14)


def test_next_solar_for_solar_already_passed():
    """今年日期已过 → 返回明年。"""
    from tools.skills.notification.remind import _next_solar_for_solar
    today = date(2026, 3, 1)
    result = _next_solar_for_solar(2, 14, today)
    assert result == date(2027, 2, 14)


def test_next_solar_for_solar_exact_today():
    """今天正好是目标日期 → 返回今年（>=today）。"""
    from tools.skills.notification.remind import _next_solar_for_solar
    today = date(2026, 2, 14)
    result = _next_solar_for_solar(2, 14, today)
    assert result == date(2026, 2, 14)


def test_next_solar_for_solar_white_valentine():
    """3月14日白色情人节。"""
    from tools.skills.notification.remind import _next_solar_for_solar
    today = date(2026, 1, 1)
    result = _next_solar_for_solar(3, 14, today)
    assert result == date(2026, 3, 14)


# ═══════════════════════════════════════════════════════════════
# calendar_checker.py — _matches_today with solar_date
# ═══════════════════════════════════════════════════════════════

def _make_solar_entry(solar_month, solar_day, advance_days=3, time="21:00", last_notified=None):
    return {
        "id": "test-solar-001",
        "type": "solar_date",
        "solar_month": solar_month,
        "solar_day": solar_day,
        "advance_days": advance_days,
        "time": time,
        "message": "准备礼物",
        "label": f"每年{solar_month}月{solar_day}日",
        "session_key": "test",
        "last_notified_date": last_notified,
    }


def test_solar_matches_advance_day():
    """提前3天：2月11日应触发2月14日情人节提醒。"""
    from calendar_checker import _matches_today
    entry = _make_solar_entry(2, 14, advance_days=3)
    assert _matches_today(entry, date(2026, 2, 11)) is True


def test_solar_does_not_match_early():
    """提前3天：2月10日不触发（还差4天）。"""
    from calendar_checker import _matches_today
    entry = _make_solar_entry(2, 14, advance_days=3)
    assert _matches_today(entry, date(2026, 2, 10)) is False


def test_solar_does_not_match_after():
    """情人节当天（超过提醒日）不触发。"""
    from calendar_checker import _matches_today
    entry = _make_solar_entry(2, 14, advance_days=3)
    assert _matches_today(entry, date(2026, 2, 14)) is False


def test_solar_matches_zero_advance():
    """advance_days=0：当天触发。"""
    from calendar_checker import _matches_today
    entry = _make_solar_entry(2, 14, advance_days=0)
    assert _matches_today(entry, date(2026, 2, 14)) is True


def test_solar_crosses_year_boundary():
    """今年已过 → 明年正确触发。2026-03-01，3-14需要等2026-03-14，提前3天=2026-03-11。"""
    from calendar_checker import _matches_today
    entry = _make_solar_entry(3, 14, advance_days=3)
    assert _matches_today(entry, date(2026, 3, 11)) is True


def test_solar_crosses_year_boundary_already_passed():
    """今年3月14日已过（今天3月15日），明年3月11日才触发。"""
    from calendar_checker import _matches_today
    entry = _make_solar_entry(3, 14, advance_days=3)
    today = date(2026, 3, 15)
    # 今年已过，明年提醒日 = 2027-03-11
    assert _matches_today(entry, today) is False
    assert _matches_today(entry, date(2027, 3, 11)) is True


def test_solar_wrong_type_returns_false():
    """type 不是 solar_date → 返回 False。"""
    from calendar_checker import _matches_today
    entry = {"type": "unknown", "solar_month": 2, "solar_day": 14}
    assert _matches_today(entry, date(2026, 2, 11)) is False


def test_solar_missing_fields_returns_false():
    """solar_month/solar_day 缺失 → 返回 False。"""
    from calendar_checker import _matches_today
    entry = {"type": "solar_date", "solar_month": 0, "solar_day": 0, "advance_days": 0}
    assert _matches_today(entry, date(2026, 2, 14)) is False


# ═══════════════════════════════════════════════════════════════
# remind.py handle — solar 参数写入
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_remind_solar_writes_entry(tmp_path):
    """solar 参数 → 写入 calendar_reminders.json，返回成功消息。"""
    import tools.skills.notification.remind as remind_mod
    orig_path = remind_mod._CALENDAR_REMINDERS_PATH
    remind_mod._CALENDAR_REMINDERS_PATH = tmp_path / "calendar_reminders.json"
    try:
        ctx = MagicMock()
        ctx.session_key = "test"
        result = await remind_mod.handle({
            "solar": "2-14",
            "advance_days": 3,
            "time": "21:00",
            "message": "准备礼物，情人节快到了",
        }, ctx)
        assert "公历年度提醒已设置" in result
        assert "2月14日" in result
        assert "提前3天" in result
        assert "21:00" in result

        data = json.loads((tmp_path / "calendar_reminders.json").read_text())
        assert len(data) == 1
        assert data[0]["type"] == "solar_date"
        assert data[0]["solar_month"] == 2
        assert data[0]["solar_day"] == 14
        assert data[0]["advance_days"] == 3
        assert data[0]["time"] == "21:00"
    finally:
        remind_mod._CALENDAR_REMINDERS_PATH = orig_path


@pytest.mark.asyncio
async def test_remind_solar_invalid_format(tmp_path):
    """solar 格式非法 → 返回 error。"""
    import tools.skills.notification.remind as remind_mod
    ctx = MagicMock()
    result = await remind_mod.handle({"solar": "February-14", "message": "test"}, ctx)
    assert "[error]" in result


@pytest.mark.asyncio
async def test_remind_solar_invalid_date(tmp_path):
    """solar 日期非法（如13-14）→ 返回 error。"""
    import tools.skills.notification.remind as remind_mod
    ctx = MagicMock()
    result = await remind_mod.handle({"solar": "13-14", "message": "test"}, ctx)
    assert "[error]" in result


@pytest.mark.asyncio
async def test_remind_white_valentine(tmp_path):
    """白色情人节 3-14 提前3天晚21:00。"""
    import tools.skills.notification.remind as remind_mod
    orig_path = remind_mod._CALENDAR_REMINDERS_PATH
    remind_mod._CALENDAR_REMINDERS_PATH = tmp_path / "calendar_reminders.json"
    try:
        ctx = MagicMock()
        ctx.session_key = "test"
        result = await remind_mod.handle({
            "solar": "3-14",
            "advance_days": 3,
            "time": "21:00",
            "message": "准备礼物，白色情人节快到了",
        }, ctx)
        assert "公历年度提醒已设置" in result
        assert "3月14日" in result

        data = json.loads((tmp_path / "calendar_reminders.json").read_text())
        assert data[0]["solar_month"] == 3
        assert data[0]["solar_day"] == 14
    finally:
        remind_mod._CALENDAR_REMINDERS_PATH = orig_path


# ═══════════════════════════════════════════════════════════════
# _write_calendar_reminder — upsert 保留 last_notified_date
# ═══════════════════════════════════════════════════════════════

def test_upsert_preserves_last_notified_date(tmp_path):
    """更新已有提醒时，last_notified_date 应保留，不被清零，防止当天重复触发。"""
    import tools.skills.notification.remind as remind_mod
    orig_path = remind_mod._CALENDAR_REMINDERS_PATH
    remind_mod._CALENDAR_REMINDERS_PATH = tmp_path / "calendar_reminders.json"
    try:
        initial = {
            "id": "old-id",
            "type": "solar_date",
            "solar_month": 2,
            "solar_day": 14,
            "advance_days": 3,
            "time": "21:00",
            "message": "准备礼物",
            "label": "每年2月14日提前3天",
            "session_key": "test",
            "last_notified_date": "2026-02-11",
        }
        remind_mod._CALENDAR_REMINDERS_PATH.write_text(
            json.dumps([initial], ensure_ascii=False), encoding="utf-8"
        )

        # 用户修改了 advance_days（新 entry 中 last_notified_date=None）
        updated = dict(initial)
        updated["id"] = "new-id"
        updated["advance_days"] = 5
        updated["last_notified_date"] = None

        remind_mod._write_calendar_reminder(updated)

        data = json.loads(remind_mod._CALENDAR_REMINDERS_PATH.read_text())
        assert len(data) == 1, "upsert 后应只有 1 条，不能重复追加"
        assert data[0]["advance_days"] == 5, "参数应更新"
        assert data[0]["last_notified_date"] == "2026-02-11", \
            "last_notified_date 应从旧条目保留，不能被清零"
    finally:
        remind_mod._CALENDAR_REMINDERS_PATH = orig_path


def test_upsert_new_entry_has_no_last_notified(tmp_path):
    """全新条目（无旧记录）写入时，last_notified_date 应为 None。"""
    import tools.skills.notification.remind as remind_mod
    orig_path = remind_mod._CALENDAR_REMINDERS_PATH
    remind_mod._CALENDAR_REMINDERS_PATH = tmp_path / "calendar_reminders.json"
    try:
        entry = {
            "id": "brand-new",
            "type": "solar_date",
            "solar_month": 3,
            "solar_day": 14,
            "advance_days": 3,
            "time": "21:00",
            "message": "白色情人节",
            "label": "每年3月14日提前3天",
            "session_key": "test",
            "last_notified_date": None,
        }
        remind_mod._write_calendar_reminder(entry)
        data = json.loads(remind_mod._CALENDAR_REMINDERS_PATH.read_text())
        assert len(data) == 1
        assert data[0]["last_notified_date"] is None
    finally:
        remind_mod._CALENDAR_REMINDERS_PATH = orig_path
