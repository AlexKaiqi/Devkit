"""contacts tool — 读写本地通讯录（implementation/data/contacts.yml）。"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml

from tools import tool

_CST = timezone(timedelta(hours=8))
_DATA_FILE = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[5]))) / "implementation/data/contacts.yml"


def _load() -> list[dict]:
    if not _DATA_FILE.exists():
        return []
    data = yaml.safe_load(_DATA_FILE.read_text(encoding="utf-8")) or {}
    return data.get("contacts", [])


def _save(contacts: list[dict]) -> None:
    existing = yaml.safe_load(_DATA_FILE.read_text(encoding="utf-8")) if _DATA_FILE.exists() else {}
    if not isinstance(existing, dict):
        existing = {}
    existing["contacts"] = contacts
    _DATA_FILE.write_text(yaml.dump(existing, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")


def _match(contact: dict, query: str) -> bool:
    q = query.lower()
    return any(
        q in str(contact.get(f, "")).lower()
        for f in ("name", "org", "tags", "notes", "email", "phone")
    )


def _fmt(c: dict, detail: bool = False) -> str:
    parts = [c.get("name", "(unnamed)")]
    if c.get("relation"):
        parts.append(f"[{c['relation']}]")
    if c.get("org"):
        parts.append(f"@ {c['org']}")
    if detail:
        for f in ("phone", "email", "birthday", "tags", "notes", "last_contact"):
            v = c.get(f)
            if v:
                parts.append(f"\n  {f}: {v}")
    else:
        if c.get("phone"):
            parts.append(f"📱{c['phone']}")
        if c.get("email"):
            parts.append(f"✉{c['email']}")
    return " ".join(parts)


@tool(
    name="contacts",
    description=(
        "读写本地通讯录（contacts.yml）。"
        "action='list': 列出全部或按关键词搜索。"
        "action='show': 显示某人完整信息。"
        "action='add': 新增联系人。"
        "action='update': 更新联系人字段。"
        "action='birthdays': 列出近期生日（默认 30 天内）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "show", "add", "update", "birthdays"],
            },
            "query": {"type": "string", "description": "搜索关键词（list/show/update 时使用）"},
            "contact": {
                "type": "object",
                "description": "联系人数据（add/update 时使用）。字段：name, relation, phone, email, birthday(YYYY-MM-DD), org, tags, notes, contact_freq",
            },
            "days": {"type": "integer", "description": "birthdays: 查询未来多少天内的生日（默认 30）"},
        },
        "required": ["action"],
    },
)
async def handle(args: dict, ctx) -> str:
    action = args["action"]
    query = args.get("query", "").strip()
    contacts = _load()

    if action == "list":
        results = [c for c in contacts if not query or _match(c, query)]
        if not results:
            return "(通讯录为空)" if not query else f"未找到匹配「{query}」的联系人"
        return "\n".join(_fmt(c) for c in results)

    elif action == "show":
        if not query:
            return "[error] 请提供查询关键词"
        results = [c for c in contacts if _match(c, query)]
        if not results:
            return f"未找到「{query}」"
        return "\n\n".join(_fmt(c, detail=True) for c in results)

    elif action == "add":
        contact: dict = args.get("contact") or {}
        if not contact.get("name"):
            return "[error] name 为必填项"
        contacts.append(contact)
        _save(contacts)
        return f"已添加联系人：{contact['name']}"

    elif action == "update":
        if not query:
            return "[error] 请提供要更新的联系人姓名"
        updates: dict = args.get("contact") or {}
        updated = []
        for c in contacts:
            if _match(c, query):
                c.update({k: v for k, v in updates.items() if v is not None})
                updated.append(c["name"])
        if not updated:
            return f"未找到「{query}」"
        _save(contacts)
        return f"已更新：{', '.join(updated)}"

    elif action == "birthdays":
        days = int(args.get("days", 30))
        today = datetime.now(_CST).date()
        upcoming = []
        for c in contacts:
            bd_str = c.get("birthday", "")
            if not bd_str:
                continue
            try:
                bd = datetime.strptime(str(bd_str), "%Y-%m-%d").date()
                # 今年生日
                this_year = bd.replace(year=today.year)
                if this_year < today:
                    this_year = bd.replace(year=today.year + 1)
                delta = (this_year - today).days
                if 0 <= delta <= days:
                    upcoming.append((delta, c, this_year))
            except ValueError:
                continue
        if not upcoming:
            return f"未来 {days} 天内没有生日"
        upcoming.sort()
        lines = []
        for delta, c, date in upcoming:
            when = "今天" if delta == 0 else f"{delta} 天后 ({date})"
            lines.append(f"{when} — {c['name']} {c.get('relation', '')}")
        return "\n".join(lines)

    return f"[error] 未知 action: {action}"
