"""watchlist tools — add/list/remove information subscriptions."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tools import tool

DATA_PATH = Path(os.environ.get(
    "WATCHLIST_PATH",
    Path(__file__).resolve().parents[3] / "data" / "watchlist.json",
))


def _load() -> list[dict]:
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(entries: list[dict]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


@tool(
    name="watch_add",
    description="添加信息监控订阅。用户说'帮我盯着XXX''有更新提醒我'时调用。返回 watch_id。",
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "监控主题描述，如'A股沪深300行情'"},
            "query": {"type": "string", "description": "搜索关键词"},
            "interval_hours": {"type": "number", "description": "检查间隔小时数（默认24）"},
        },
        "required": ["topic", "query"],
    },
)
async def watch_add(args: dict, ctx) -> str:
    topic = args["topic"].strip()
    query = args["query"].strip()
    interval_hours = float(args.get("interval_hours", 24))

    entries = _load()
    watch_id = str(uuid.uuid4())[:8]
    entry = {
        "watch_id": watch_id,
        "topic": topic,
        "query": query,
        "interval_hours": interval_hours,
        "session_key": ctx.session_key,
        "last_checked_at": "1970-01-01T00:00:00+00:00",
        "last_result_hash": "",
    }
    entries.append(entry)
    _save(entries)
    return json.dumps({"watch_id": watch_id, "topic": topic, "interval_hours": interval_hours}, ensure_ascii=False)


@tool(
    name="watch_list",
    description="列出所有当前信息订阅。",
    parameters={"type": "object", "properties": {}},
)
async def watch_list(args: dict, ctx) -> str:
    entries = _load()
    if not entries:
        return "当前没有任何订阅。"
    lines = ["当前订阅列表："]
    for e in entries:
        lines.append(
            f"- [{e['watch_id']}] {e['topic']} (关键词: {e['query']}, "
            f"每{e['interval_hours']}小时检查, 上次: {e.get('last_checked_at', '从未')})"
        )
    return "\n".join(lines)


@tool(
    name="watch_remove",
    description="删除信息订阅。",
    parameters={
        "type": "object",
        "properties": {
            "watch_id": {"type": "string", "description": "要删除的订阅 watch_id"},
        },
        "required": ["watch_id"],
    },
)
async def watch_remove(args: dict, ctx) -> str:
    watch_id = args["watch_id"].strip()
    entries = _load()
    before = len(entries)
    entries = [e for e in entries if e["watch_id"] != watch_id]
    if len(entries) == before:
        return f"[error] 未找到 watch_id={watch_id}"
    _save(entries)
    return f"已删除订阅 {watch_id}"
