"""schedule tool — 希露菲的个人日程/事件存储，不依赖系统日历。

数据文件：implementation/data/schedule.json
格式：[{"id": "...", "datetime": "YYYY-MM-DD HH:MM", "title": "...", "note": "...", "created_at": "..."}]
"""

import json
import re
import uuid
from datetime import datetime, timezone, timedelta


def _parse_dt(s: str) -> datetime | None:
    """Parse 'YYYY-MM-DD HH:MM' without strptime to avoid stdlib calendar shadowing."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", s.strip())
    if not m:
        return None
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]),
                        tzinfo=_CST)
    except ValueError:
        return None
from pathlib import Path

from tools import tool

_CST = timezone(timedelta(hours=8))
_DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "schedule.json"


# ── 持久化 ───────────────────────────────────────────────────

def _load() -> list[dict]:
    if not _DATA_FILE.exists():
        return []
    try:
        return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(events: list[dict]) -> None:
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(
        json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 工具 ─────────────────────────────────────────────────────

@tool(
    name="schedule",
    description=(
        "Manage personal schedule/events (stored locally, no external calendar needed). "
        "action='add': record a new event (datetime + title required). "
        "action='list': query upcoming events; optional date filter 'YYYY-MM-DD' or 'YYYY-MM-DD to YYYY-MM-DD'. "
        "action='delete': remove event by id."
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "delete"],
                "description": "add / list / delete",
            },
            "datetime": {
                "type": "string",
                "description": "Event datetime 'YYYY-MM-DD HH:MM' (CST). Required for add.",
            },
            "title": {
                "type": "string",
                "description": "Event title. Required for add.",
            },
            "note": {
                "type": "string",
                "description": "Optional extra details for the event.",
            },
            "date_filter": {
                "type": "string",
                "description": "For list: 'YYYY-MM-DD' (single day) or 'YYYY-MM-DD to YYYY-MM-DD' (range). Omit for all upcoming.",
            },
            "id": {
                "type": "string",
                "description": "Event id. Required for delete.",
            },
        },
        "required": ["action"],
    },
)
async def handle(args: dict, ctx) -> str:
    action = args.get("action", "list")
    now = datetime.now(_CST)

    if action == "add":
        dt_str = args.get("datetime", "").strip()
        title = args.get("title", "").strip()
        if not dt_str:
            return "[error] datetime is required for add"
        if not title:
            return "[error] title is required for add"

        # 验证格式
        dt = _parse_dt(dt_str)
        if dt is None:
            return f"[error] Invalid datetime format: '{dt_str}'. Use 'YYYY-MM-DD HH:MM'."

        event = {
            "id": str(uuid.uuid4())[:8],
            "datetime": dt_str,
            "title": title,
            "note": args.get("note", ""),
            "created_at": now.strftime("%Y-%m-%d %H:%M"),
        }
        events = _load()
        events.append(event)
        # 按时间排序
        events.sort(key=lambda e: e.get("datetime", ""))
        _save(events)

        weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][dt.weekday()]
        return f"已记录：{dt_str} ({weekday_cn}) {title}（id={event['id']}）"

    elif action == "list":
        events = _load()
        date_filter = args.get("date_filter", "").strip()

        if date_filter:
            # 解析日期范围
            range_match = re.match(r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", date_filter)
            single_match = re.match(r"(\d{4}-\d{2}-\d{2})$", date_filter)
            if range_match:
                start_d, end_d = range_match.group(1), range_match.group(2)
                events = [e for e in events if start_d <= e.get("datetime", "")[:10] <= end_d]
            elif single_match:
                d = single_match.group(1)
                events = [e for e in events if e.get("datetime", "").startswith(d)]
            else:
                return f"[error] Invalid date_filter: '{date_filter}'. Use 'YYYY-MM-DD' or 'YYYY-MM-DD to YYYY-MM-DD'."
        else:
            # 默认只显示未来事件
            today_str = now.strftime("%Y-%m-%d")
            events = [e for e in events if e.get("datetime", "") >= today_str]

        if not events:
            return "没有找到相关日程。"

        lines = []
        for e in events:
            dt_str = e.get("datetime", "")
            dt = _parse_dt(dt_str)
            if dt:
                weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][dt.weekday()]
                dt_label = f"{dt_str} ({weekday_cn})"
            else:
                dt_label = dt_str
            note = f" — {e['note']}" if e.get("note") else ""
            lines.append(f"[{e['id']}] {dt_label} {e['title']}{note}")
        return "\n".join(lines)

    elif action == "delete":
        event_id = args.get("id", "").strip()
        if not event_id:
            return "[error] id is required for delete"
        events = _load()
        before = len(events)
        events = [e for e in events if e.get("id") != event_id]
        if len(events) == before:
            return f"[error] Event id '{event_id}' not found"
        _save(events)
        return f"已删除事件 id={event_id}"

    return f"[error] Unknown action: {action}"
