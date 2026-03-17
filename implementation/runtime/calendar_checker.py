"""CalendarChecker — 农历节日与自定义农历日期提醒后台检查器。

类比 WatchlistChecker，每隔 interval_sec 秒扫描 data_path（calendar_reminders.json），
判断今天或今天之后 advance_days 天内是否命中，若命中则通过 notify 工具发送通知。
使用 last_notified_date（YYYY-MM-DD）防止同一触发日重复通知。
"""

import asyncio
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Awaitable

log = logging.getLogger("calendar-checker")

# ── 内置节日表（农历 month, day） ────────────────────────────
BUILTIN_HOLIDAYS: dict[str, tuple[int, int]] = {
    "春节":  (1, 1),
    "元宵节": (1, 15),
    "端午节": (5, 5),
    "七夕节": (7, 7),
    "中秋节": (8, 15),
    "重阳节": (9, 9),
    "腊八节": (12, 8),
}


def _lunar_to_solar(year: int, lunar_month: int, lunar_day: int) -> date | None:
    """将农历日期转换为公历日期。返回 None 表示转换失败。"""
    try:
        from lunardate import LunarDate
        ld = LunarDate(year, lunar_month, lunar_day)
        sd = ld.toSolarDate()
        return sd
    except Exception as e:
        log.debug("lunar_to_solar(%d, %d, %d) failed: %s", year, lunar_month, lunar_day, e)
        return None


def next_solar_date_for_lunar(
    lunar_month: int, lunar_day: int, today: date | None = None
) -> date | None:
    """返回该农历日期在今年或明年对应的下一个公历日期。"""
    if today is None:
        today = date.today()
    for delta_year in (0, 1):
        year = today.year + delta_year
        sd = _lunar_to_solar(year, lunar_month, lunar_day)
        if sd and sd >= today:
            return sd
    return None


def next_solar_date_for_holiday(
    name: str, today: date | None = None
) -> date | None:
    """返回内置节日在今年或明年的下一个公历日期。未知节日返回 None。"""
    if name not in BUILTIN_HOLIDAYS:
        return None
    lm, ld = BUILTIN_HOLIDAYS[name]
    return next_solar_date_for_lunar(lm, ld, today)


def _next_solar_date_for_solar(
    solar_month: int, solar_day: int, today: date | None = None
) -> date | None:
    """返回公历固定日期（M月D日）今年或明年的下一个日期。"""
    if today is None:
        today = date.today()
    for delta in (0, 1):
        year = today.year + delta
        try:
            d = date(year, solar_month, solar_day)
            if d >= today:
                return d
        except ValueError:
            continue
    return None


def _matches_today(entry: dict, today: date) -> bool:
    """判断该条目是否应在 today 触发通知。"""
    intent_type = entry.get("type", "")
    advance_days = int(entry.get("advance_days", 0))

    if intent_type == "holiday":
        name = entry.get("name", "")
        target = next_solar_date_for_holiday(name, today)
    elif intent_type == "lunar_date":
        lm = int(entry.get("lunar_month", 0))
        ld = int(entry.get("lunar_day", 0))
        if not lm or not ld:
            return False
        target = next_solar_date_for_lunar(lm, ld, today)
    elif intent_type == "solar_date":
        sm = int(entry.get("solar_month", 0))
        sd = int(entry.get("solar_day", 0))
        if not sm or not sd:
            return False
        target = _next_solar_date_for_solar(sm, sd, today)
    else:
        return False

    if target is None:
        return False

    # 提醒日 = target - advance_days
    remind_date = target - timedelta(days=advance_days)
    return remind_date == today


class CalendarChecker:
    """Periodically checks calendar reminders and fires notifications when due."""

    def __init__(
        self,
        data_path: Path,
        run_tool_fn: Callable[..., Awaitable[str]],
        interval_sec: int = 3600,
    ):
        self._data_path = data_path
        self._run_tool = run_tool_fn
        self._interval_sec = interval_sec

    async def start(self) -> None:
        asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        # 启动时立即检查一次，避免重启后错过当天提醒（Bug 1 fix）
        try:
            await self._check_all()
        except Exception:
            log.exception("CalendarChecker._check_all error (startup)")
        while True:
            try:
                await asyncio.sleep(self._interval_sec)
                await self._check_all()
            except asyncio.CancelledError:
                raise  # 让任务正常取消（Bug 6 fix）
            except Exception:
                log.exception("CalendarChecker._check_all error")

    async def _check_all(self, _now_cst=None) -> None:
        if not self._data_path.exists():
            return

        try:
            entries = json.loads(self._data_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Failed to read calendar_reminders data")
            return

        from datetime import datetime, timezone, timedelta
        _CST = timezone(timedelta(hours=8))
        if _now_cst is None:
            _now_cst = datetime.now(_CST)

        # today 从 _now_cst 派生，避免跨午夜时两者日期不一致
        today = _now_cst.date()
        today_str = today.isoformat()
        changed = False

        for entry in entries:
            # 防重复：当天已通知过则跳过
            if entry.get("last_notified_date") == today_str:
                continue

            # 检查是否命中
            if not _matches_today(entry, today):
                continue

            # 检查触发时间（hour:minute）：当前时间必须在设定时间的 [0, +120min] 窗口内
            # 避免深夜重启后补发当天早间提醒
            time_str = entry.get("time", "09:00")
            try:
                hh, mm = map(int, time_str.split(":"))
            except Exception:
                hh, mm = 9, 0
            trigger_minutes = hh * 60 + mm
            now_minutes = _now_cst.hour * 60 + _now_cst.minute
            elapsed = now_minutes - trigger_minutes
            if elapsed < 0 or elapsed > 120:
                continue  # 未到触发时间，或已超过 2 小时窗口

            # 构建通知消息
            message = entry.get("message", "")
            intent_type = entry.get("type", "")
            if not message:
                if intent_type == "holiday":
                    name = entry.get("name", "节日")
                    adv = int(entry.get("advance_days", 0))
                    adv_str = "今天" if adv == 0 else ("明天" if adv == 1 else f"{adv}天后")
                    message = f"提醒：{name}{adv_str}到了，记得做准备！"
                elif intent_type == "lunar_date":
                    lm = entry.get("lunar_month", "?")
                    ld = entry.get("lunar_day", "?")
                    adv = int(entry.get("advance_days", 0))
                    label = entry.get("label", f"农历{lm}月{ld}日")
                    adv_str = "今天" if adv == 0 else ("明天" if adv == 1 else f"{adv}天后")
                    message = f"提醒：{label}{adv_str}即将到来！"
                elif intent_type == "solar_date":
                    sm = entry.get("solar_month", "?")
                    sd = entry.get("solar_day", "?")
                    adv = int(entry.get("advance_days", 0))
                    label = entry.get("label", f"每年{sm}月{sd}日")
                    adv_str = "今天" if adv == 0 else ("明天" if adv == 1 else f"{adv}天后")
                    message = f"提醒：{label}{adv_str}即将到来！"

            session_key = entry.get("session_key", "")

            try:
                await self._run_tool("notify", {"message": message}, session_key=session_key)
                log.info("CalendarChecker: notified for entry id=%s", entry.get("id", "?"))
            except Exception as e:
                log.warning("CalendarChecker notify failed: %s", e)
                continue

            entry["last_notified_date"] = today_str
            changed = True

        if changed:
            try:
                self._data_path.write_text(
                    json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                log.warning("Failed to save calendar_reminders after check")
