"""note tool — 追加一条记录到今日日志。"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from tools import tool

_CST = timezone(timedelta(hours=8))
_PERSONA_DIR = Path(os.environ.get("WORKSPACE_DIR", "implementation/assets/persona"))
if not _PERSONA_DIR.is_absolute():
    _PERSONA_DIR = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[5]))) / _PERSONA_DIR


def _memory_dir() -> Path:
    d = _PERSONA_DIR / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


@tool(
    name="note",
    description="追加一条记录到今日日志（memory/YYYY-MM-DD.md）。适合临时备忘、想法、当日日志。",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "要记录的内容"},
            "category": {
                "type": "string",
                "description": "分类标签（可选），如 idea / todo / log / insight",
            },
        },
        "required": ["content"],
    },
    action_only=True,
)
async def handle(args: dict, ctx) -> str:
    content = args["content"].strip()
    category = args.get("category", "").strip()

    now = datetime.now(_CST)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    log_file = _memory_dir() / f"{date_str}.md"

    # 初始化文件头
    if not log_file.exists():
        log_file.write_text(f"# {date_str}\n\n", encoding="utf-8")

    tag = f" `{category}`" if category else ""
    entry = f"- {time_str}{tag} {content}\n"

    with log_file.open("a", encoding="utf-8") as f:
        f.write(entry)

    return f"已记录到 {date_str}.md：{entry.strip()}"
