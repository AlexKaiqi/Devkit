"""remind tool — set a deferred reminder via Timer API."""

import asyncio
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiohttp

from tools import tool

TIMER_API = f"http://localhost:{os.environ.get('TIMER_API_PORT', '8789')}"
_CST = timezone(timedelta(hours=8))


def _parse_delay(s: str) -> int | None:
    """Parse delay string to seconds.

    Accepts:
    - Relative: '5m', '2h', '1h30m', '1d', '90' (seconds)
    - Absolute: 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM:SS' (CST)
    """
    s = s.strip()

    # Absolute datetime: YYYY-MM-DD HH:MM (avoid strptime to sidestep stdlib calendar shadowing)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        try:
            target = datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]),
                              int(m[6] or 0), tzinfo=_CST)
            delay = int((target - datetime.now(_CST)).total_seconds())
            return delay if delay > 0 else None
        except ValueError:
            pass

    # Relative: pure integer = seconds
    if s.isdigit():
        return int(s)

    # Relative: e.g. '5m', '2h', '1h30m', '1d'
    s_lower = s.lower()
    total = 0
    for value, unit in re.findall(r"(\d+)\s*([smhd])", s_lower):
        v = int(value)
        if unit == "s":
            total += v
        elif unit == "m":
            total += v * 60
        elif unit == "h":
            total += v * 3600
        elif unit == "d":
            total += v * 86400
    return total if total > 0 else None


@tool(
    name="remind",
    description=(
        "Set a reminder that fires at a specific time or after a delay. "
        "delay: relative ('5m', '2h', '1h30m', '1d') OR absolute datetime 'YYYY-MM-DD HH:MM' (CST). "
        "message: what to remind about. "
        "The reminder will be delivered via push notification when it fires."
    ),
    parameters={
        "type": "object",
        "properties": {
            "delay": {
                "type": "string",
                "description": "Relative delay ('5m','2h','1d') or absolute datetime 'YYYY-MM-DD HH:MM' (CST)",
            },
            "message": {"type": "string", "description": "Reminder message content"},
        },
        "required": ["delay", "message"],
    },
)
async def handle(args: dict, ctx) -> str:
    raw_delay = str(args.get("delay", ""))
    message = args.get("message", "").strip()

    if not message:
        return "[error] message is required"

    delay_sec = _parse_delay(raw_delay)
    if delay_sec is None or delay_sec <= 0:
        return f"[error] Cannot parse delay: '{raw_delay}'. Use '5m','2h','1d' or 'YYYY-MM-DD HH:MM'."

    payload = {"delay_seconds": delay_sec, "message": message}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TIMER_API}/api/timer",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
        if data.get("ok"):
            timer_id = data.get("timer_id", "?")
            h, rem = divmod(delay_sec, 3600)
            m, s = divmod(rem, 60)
            human = (f"{h}h" if h else "") + (f"{m}m" if m else "") + (f"{s}s" if s else "")
            fire_at = datetime.now(_CST) + timedelta(seconds=delay_sec)
            fire_str = fire_at.strftime("%Y-%m-%d %H:%M")
            return f"提醒已设置，将在 {fire_str} 触发（约 {human} 后，timer_id={timer_id}）"
        return f"[error] Timer API: {data}"
    except Exception as e:
        return f"[error] remind: {e}"
