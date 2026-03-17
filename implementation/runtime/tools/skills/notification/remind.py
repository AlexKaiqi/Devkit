"""remind tool — set a deferred or recurring reminder via Timer API,
or a calendar-based reminder (holiday / lunar date) via CalendarChecker."""

import json
import os
import re
import uuid
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

import aiohttp

from tools import tool

TIMER_API = f"http://localhost:{os.environ.get('TIMER_API_PORT', '8789')}"
_CST = timezone(timedelta(hours=8))

_CALENDAR_REMINDERS_PATH = Path(__file__).resolve().parents[4] / "runtime" / "data" / "calendar_reminders.json"
_SCHEDULE_FILE = Path(__file__).resolve().parents[4] / "runtime" / "data" / "schedule.json"


# ── 冲突检测 ─────────────────────────────────────────────────

def _load_schedule() -> list[dict]:
    """Read schedule.json, return list or [] on error."""
    try:
        return json.loads(_SCHEDULE_FILE.read_text(encoding="utf-8")) if _SCHEDULE_FILE.exists() else []
    except Exception:
        return []


def _parse_dt_simple(s: str) -> datetime | None:
    """Parse 'YYYY-MM-DD HH:MM' without strptime to avoid stdlib calendar shadowing."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", s.strip())
    if not m:
        return None
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), tzinfo=_CST)
    except ValueError:
        return None


def _check_conflicts(target_dt: datetime, window_min: int = 60) -> list[dict]:
    """Return schedule events within ±window_min minutes of target_dt."""
    result = []
    for e in _load_schedule():
        event_dt = _parse_dt_simple(e.get("datetime", ""))
        if event_dt and abs((event_dt - target_dt).total_seconds()) <= window_min * 60:
            result.append(e)
    return result


def _conflict_warning(conflicts: list[dict]) -> str:
    """Format conflict list as warning string (empty string if no conflicts)."""
    if not conflicts:
        return ""
    lines = ["⚠️ 附近有日程安排："]
    for e in conflicts:
        lines.append(f"  · {e.get('datetime', '?')} {e.get('title', '?')}（id={e.get('id', '?')}）")
    return "\n" + "\n".join(lines)

# 内置节日名称映射（用于验证 + 提示下次日期）
_BUILTIN_HOLIDAYS = {
    "春节": (1, 1),
    "元宵节": (1, 15),
    "端午节": (5, 5),
    "七夕节": (7, 7),
    "中秋节": (8, 15),
    "重阳节": (9, 9),
    "腊八节": (12, 8),
}


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_time(time_str: str) -> bool:
    """验证 HH:MM 格式（24h）。"""
    return bool(_TIME_RE.match(time_str.strip()))


def _parse_delay(s: str) -> int | None:
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        try:
            target = datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]),
                              int(m[6] or 0), tzinfo=_CST)
            delay = int((target - datetime.now(_CST)).total_seconds())
            return delay if delay > 0 else None
        except ValueError:
            pass
    if s.isdigit():
        return int(s)
    s_lower = s.lower()  # 兼容大写单位：1H / 30M / 2D
    total = 0
    for value, unit in re.findall(r"(\d+)\s*([smhdSMHD])", s_lower):
        v = int(value)
        if unit == "s":   total += v
        elif unit == "m": total += v * 60
        elif unit == "h": total += v * 3600
        elif unit == "d": total += v * 86400
    return total if total > 0 else None


def _next_solar_for_lunar(lunar_month: int, lunar_day: int, today: date | None = None) -> date | None:
    """返回农历日期对应的下一个公历日期（今年或明年）。"""
    if today is None:
        today = date.today()
    try:
        from lunardate import LunarDate
        for delta in (0, 1):
            year = today.year + delta
            try:
                ld = LunarDate(year, lunar_month, lunar_day)
                sd = ld.toSolarDate()
                if sd >= today:
                    return sd
            except Exception:
                continue
    except ImportError:
        pass
    return None


def _next_solar_for_holiday(name: str, today: date | None = None) -> date | None:
    """返回内置节日下一次公历日期。"""
    if name not in _BUILTIN_HOLIDAYS:
        return None
    lm, ld = _BUILTIN_HOLIDAYS[name]
    return _next_solar_for_lunar(lm, ld, today)


def _next_solar_for_solar(solar_month: int, solar_day: int, today: date | None = None) -> date | None:
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


def _fmt_remind_date(remind_date: "date | None", today: "date") -> str:
    """格式化下次触发日期，已过期时提示下个周期。"""
    if remind_date is None:
        return "（日期计算需 lunardate 库）"
    if remind_date < today:
        return "（本周期触发日已过，将在下个周期触发）"
    return f"下次触发日期：{remind_date.strftime('%Y-%m-%d')}（北京时间）"


def _write_calendar_reminder(entry: dict) -> None:
    """写入或覆盖 calendar_reminders.json 中的条目（相同类型+日期的去重）。"""
    _CALENDAR_REMINDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(_CALENDAR_REMINDERS_PATH.read_text(encoding="utf-8")) if _CALENDAR_REMINDERS_PATH.exists() else []
    except Exception:
        existing = []

    # 去重：相同语义的条目覆盖而非追加
    def _is_same(e: dict) -> bool:
        if e.get("type") != entry.get("type"):
            return False
        t = entry.get("type")
        if t == "holiday":
            return e.get("name") == entry.get("name")
        if t == "lunar_date":
            return e.get("lunar_month") == entry.get("lunar_month") and e.get("lunar_day") == entry.get("lunar_day")
        if t == "solar_date":
            return e.get("solar_month") == entry.get("solar_month") and e.get("solar_day") == entry.get("solar_day")
        return False

    # 去重：相同语义的条目覆盖而非追加；保留旧条目的 last_notified_date 防当天重复触发
    old_entry = next((e for e in existing if _is_same(e)), None)
    if old_entry is not None:
        entry["last_notified_date"] = old_entry.get("last_notified_date")

    new_list = [e for e in existing if not _is_same(e)]
    new_list.append(entry)
    # 原子写：先写临时文件，再 rename，防止写入中途崩溃导致文件损坏
    tmp = _CALENDAR_REMINDERS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(new_list, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_CALENDAR_REMINDERS_PATH)


@tool(
    name="remind",
    description=(
        "Set a one-time, recurring, or calendar-based (holiday/lunar/solar) reminder.\n"
        "For one-time: provide 'delay' (relative '5m','2h','1d' or absolute 'YYYY-MM-DD HH:MM' CST).\n"
        "For recurring: provide 'cron' as a 5-field cron expression (CST timezone), e.g.:\n"
        "  '0 9 * * 1-5'  — weekdays at 09:00\n"
        "  '0 8 * * *'    — every day at 08:00\n"
        "  '0 9 * * 1'    — every Monday at 09:00\n"
        "  '*/30 * * * *' — every 30 minutes\n"
        "For lunar festival (中秋节/春节/端午节 etc.): use 'holiday' parameter with festival name.\n"
        "For custom lunar date (e.g., birthday): use 'lunar' parameter in 'M-D' format (e.g., '3-8' = 农历三月初八).\n"
        "For fixed solar annual date (e.g., Valentine's Day, White Day): use 'solar' in 'M-D' format (e.g., '2-14', '3-14').\n"
        "Convert user's natural language schedule description to cron before calling.\n"
        "Always provide 'message' describing what to remind about."
    ),
    parameters={
        "type": "object",
        "properties": {
            "delay": {
                "type": "string",
                "description": "One-time: '5m','2h','1d' or 'YYYY-MM-DD HH:MM'. Omit when using cron/holiday/lunar.",
            },
            "cron": {
                "type": "string",
                "description": "Recurring: 5-field cron in CST, e.g. '0 9 * * 1-5'. Omit when using delay/holiday/lunar.",
            },
            "label": {
                "type": "string",
                "description": "Human-readable schedule label, e.g. '工作日早9点'.",
            },
            "holiday": {
                "type": "string",
                "description": "节日名称，如 '中秋节'、'春节'、'端午节'。支持：春节、元宵节、端午节、七夕节、中秋节、重阳节、腊八节。",
            },
            "lunar": {
                "type": "string",
                "description": "农历日期，格式 'M-D'，如 '3-8' 表示农历三月初八。",
            },
            "advance_days": {
                "type": "integer",
                "description": "提前天数（用于 holiday/lunar/solar），默认 0 表示当天提醒，1 表示提前一天。",
            },
            "time": {
                "type": "string",
                "description": "触发时间 'HH:MM'（24h，CST），用于 holiday/lunar/solar，默认 '09:00'。",
            },
            "message": {"type": "string", "description": "Reminder message content"},
            "solar": {
                "type": "string",
                "description": "公历固定年度日期，格式 'M-D'，如 '2-14' 表示每年2月14日（情人节）、'3-14' 表示白色情人节。与 advance_days/time 配合使用。",
            },
        },
        "required": ["message"],
    },
    action_only=True,
)
async def handle(args: dict, ctx) -> str:
    message = args.get("message", "").strip()
    cron_expr = args.get("cron", "").strip()
    raw_delay = str(args.get("delay", "")).strip()
    label = args.get("label", "").strip()
    holiday = args.get("holiday", "").strip()
    lunar = args.get("lunar", "").strip()
    solar = args.get("solar", "").strip()
    try:
        advance_days = int(args.get("advance_days", 0))
    except (ValueError, TypeError):
        return "[error] advance_days 必须是整数，如 0、1、3"
    time_str = args.get("time", "09:00").strip()

    if not message:
        return "[error] message is required"

    # ── 农历节日 ────────────────────────────────────────────
    if holiday:
        # 校验 advance_days / time（仅 calendar 类型需要）
        if not (0 <= advance_days <= 365):
            return "[error] advance_days 必须在 0–365 之间"
        if not _validate_time(time_str):
            return f"[error] time 格式不合法，应为 'HH:MM'（24小时制），如 '09:00' / '21:30'，当前值：'{time_str}'"

        if holiday not in _BUILTIN_HOLIDAYS:
            known = "、".join(_BUILTIN_HOLIDAYS.keys())
            return f"[error] 未知节日 '{holiday}'，支持的节日：{known}"

        today = datetime.now(_CST).date()
        next_date = _next_solar_for_holiday(holiday, today)
        remind_date = (next_date - timedelta(days=advance_days)) if next_date else None

        entry = {
            "id": str(uuid.uuid4()),
            "type": "holiday",
            "name": holiday,
            "advance_days": advance_days,
            "time": time_str,
            "message": message,
            "session_key": getattr(ctx, "session_key", ""),
            "last_notified_date": None,
            "label": f"{holiday}{'提前' + str(advance_days) + '天' if advance_days else '当天'}",
        }
        try:
            _write_calendar_reminder(entry)
        except Exception as e:
            return f"[error] 写入日历提醒失败: {e}"

        if remind_date:
            return (
                f"节日提醒已设置：{holiday}\n"
                f"{'提前' + str(advance_days) + '天' if advance_days else '当天'} {time_str} 提醒\n"
                f"{_fmt_remind_date(remind_date, today)}"
            )
        return f"节日提醒已设置：{holiday}，提前{advance_days}天 {time_str} 提醒{_fmt_remind_date(None, today)}"

    # ── 自定义农历日期 ───────────────────────────────────────
    if lunar:
        if not (0 <= advance_days <= 365):
            return "[error] advance_days 必须在 0–365 之间"
        if not _validate_time(time_str):
            return f"[error] time 格式不合法，应为 'HH:MM'（24小时制），如 '09:00' / '21:30'，当前值：'{time_str}'"

        m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", lunar.strip())
        if not m:
            return f"[error] lunar 格式应为 'M-D'，如 '3-8' 表示农历三月初八，当前值：'{lunar}'"
        lm, ld = int(m.group(1)), int(m.group(2))

        today = datetime.now(_CST).date()
        next_date = _next_solar_for_lunar(lm, ld, today)
        remind_date = (next_date - timedelta(days=advance_days)) if next_date else None

        label_text = args.get("label") or (
            f"农历{lm}月{ld}日{'提前' + str(advance_days) + '天' if advance_days else '当天'}"
        )
        entry = {
            "id": str(uuid.uuid4()),
            "type": "lunar_date",
            "lunar_month": lm,
            "lunar_day": ld,
            "advance_days": advance_days,
            "time": time_str,
            "message": message,
            "label": label_text,
            "session_key": getattr(ctx, "session_key", ""),
            "last_notified_date": None,
        }
        try:
            _write_calendar_reminder(entry)
        except Exception as e:
            return f"[error] 写入日历提醒失败: {e}"

        if remind_date:
            return (
                f"农历日期提醒已设置：农历{lm}月{ld}日\n"
                f"{'提前' + str(advance_days) + '天' if advance_days else '当天'} {time_str} 提醒\n"
                f"{_fmt_remind_date(remind_date, today)}"
            )
        return f"农历日期提醒已设置：农历{lm}月{ld}日，提前{advance_days}天 {time_str} 提醒{_fmt_remind_date(None, today)}"

    # ── 公历固定年度日期 ─────────────────────────────────────
    if solar:
        if not (0 <= advance_days <= 365):
            return "[error] advance_days 必须在 0–365 之间"
        if not _validate_time(time_str):
            return f"[error] time 格式不合法，应为 'HH:MM'（24小时制），如 '09:00' / '21:30'，当前值：'{time_str}'"

        m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", solar.strip())
        if not m:
            return f"[error] solar 格式应为 'M-D'，如 '2-14' 表示每年2月14日，当前值：'{solar}'"
        sm, sd = int(m.group(1)), int(m.group(2))
        try:
            date(2000, sm, sd)  # 验证日期合法性
        except ValueError:
            return f"[error] solar '{solar}' 不是合法日期（月份1-12，日合法范围内）"

        today = datetime.now(_CST).date()
        next_date = _next_solar_for_solar(sm, sd, today)
        remind_date = (next_date - timedelta(days=advance_days)) if next_date else None

        label_text = args.get("label") or (
            f"每年{sm}月{sd}日{'提前' + str(advance_days) + '天' if advance_days else '当天'}"
        )
        entry = {
            "id": str(uuid.uuid4()),
            "type": "solar_date",
            "solar_month": sm,
            "solar_day": sd,
            "advance_days": advance_days,
            "time": time_str,
            "message": message,
            "label": label_text,
            "session_key": getattr(ctx, "session_key", ""),
            "last_notified_date": None,
        }
        try:
            _write_calendar_reminder(entry)
        except Exception as e:
            return f"[error] 写入日历提醒失败: {e}"

        if remind_date:
            return (
                f"公历年度提醒已设置：每年{sm}月{sd}日\n"
                f"{'提前' + str(advance_days) + '天' if advance_days else '当天'} {time_str} 提醒\n"
                f"{_fmt_remind_date(remind_date, today)}"
            )
        return f"公历年度提醒已设置：每年{sm}月{sd}日，提前{advance_days}天 {time_str} 提醒"

    # ── 普通 timer（cron / once） ───────────────────────────
    if not cron_expr and not raw_delay:
        return "[error] 请提供 delay（一次性）、cron（周期性）、holiday（节日）、lunar（农历日期）或 solar（公历年度日期）参数。"

    # cron 表达式本地预校验，避免把无效表达式传给 Timer API
    if cron_expr:
        try:
            from croniter import croniter
            if not croniter.is_valid(cron_expr):
                return f"[error] cron 表达式无效：'{cron_expr}'，示例：'0 9 * * 1-5'（工作日9点）"
        except Exception:
            return f"[error] cron 表达式无效：'{cron_expr}'"

    try:
        async with aiohttp.ClientSession() as session:
            if cron_expr:
                intent = {"type": "recurring", "human": label or cron_expr}
                payload = {"cron_expr": cron_expr, "message": message, "label": label or cron_expr, "intent": intent,
                           "session_key": getattr(ctx, "session_key", "")}
                async with session.post(
                    f"{TIMER_API}/api/timer", json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()

                if data.get("ok"):
                    timer_id = data.get("timer_id", "?")
                    nxt = None
                    try:
                        from croniter import croniter
                        c = croniter(cron_expr, datetime.now(_CST))
                        nxt_naive = c.get_next(datetime)
                        # croniter 返回 naive datetime，补上 CST 时区
                        nxt = nxt_naive.replace(tzinfo=_CST)
                        next_str = nxt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        next_str = "（未知）"
                    display = label or cron_expr
                    result_msg = f"周期提醒已设置：{display}\n下次触发：{next_str}（北京时间）\ntimer_id={timer_id}"
                    if nxt:
                        conflicts = _check_conflicts(nxt, window_min=60)
                        result_msg += _conflict_warning(conflicts)
                    return result_msg
                return f"[error] Timer API: {data.get('error', data)}"

            else:
                delay_sec = _parse_delay(raw_delay)
                if delay_sec is None or delay_sec <= 0:
                    return f"[error] Cannot parse delay: '{raw_delay}'."
                intent = {"type": "once"}
                payload = {"delay_seconds": delay_sec, "message": message, "intent": intent,
                           "session_key": getattr(ctx, "session_key", "")}
                async with session.post(
                    f"{TIMER_API}/api/timer", json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()

                if data.get("ok"):
                    timer_id = data.get("timer_id", "?")
                    h, rem = divmod(delay_sec, 3600)
                    m, s = divmod(rem, 60)
                    human = (f"{h}h" if h else "") + (f"{m}m" if m else "") + (f"{s}s" if s else "")
                    fire_at = datetime.now(_CST) + timedelta(seconds=delay_sec)
                    result_msg = f"提醒已设置，将在 {fire_at.strftime('%Y-%m-%d %H:%M')} 触发（约 {human} 后，timer_id={timer_id}）"
                    conflicts = _check_conflicts(fire_at, window_min=60)
                    result_msg += _conflict_warning(conflicts)
                    return result_msg
                return f"[error] Timer API: {data.get('error', data)}"
    except Exception as e:
        return f"[error] remind: {e}"
