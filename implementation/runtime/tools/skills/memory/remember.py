"""remember tool — 追加长期记忆到 MEMORY.md。"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from tools import tool

_CST = timezone(timedelta(hours=8))
_PERSONA_DIR = Path(os.environ.get("WORKSPACE_DIR", "implementation/assets/persona"))
if not _PERSONA_DIR.is_absolute():
    _PERSONA_DIR = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[5]))) / _PERSONA_DIR


@tool(
    name="remember",
    description="将重要信息持久化到长期记忆（MEMORY.md）。适合用户偏好、关键决策、经验教训、需要跨会话保留的事实。",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "要长期记住的内容"},
            "section": {
                "type": "string",
                "description": "追加到哪个章节（可选），如 '用户偏好' / '经验教训' / '项目信息'。不填则追加到文件末尾。",
            },
        },
        "required": ["content"],
    },
)
async def handle(args: dict, ctx) -> str:
    content = args["content"].strip()
    section = args.get("section", "").strip()

    now = datetime.now(_CST)
    date_str = now.strftime("%Y-%m-%d")

    memory_file = _PERSONA_DIR / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("# 长期记忆\n\n", encoding="utf-8")

    entry = f"- [{date_str}] {content}\n"
    text = memory_file.read_text(encoding="utf-8")

    if section:
        # 找到对应章节标题并在其下追加
        marker = f"## {section}"
        if marker in text:
            idx = text.index(marker) + len(marker)
            # 跳到下一行
            nl = text.find("\n", idx)
            insert_pos = nl + 1 if nl != -1 else len(text)
            text = text[:insert_pos] + entry + text[insert_pos:]
            memory_file.write_text(text, encoding="utf-8")
            return f"已追加到「{section}」：{entry.strip()}"
        # 章节不存在则新建
        text = text.rstrip() + f"\n\n## {section}\n\n{entry}"
    else:
        text = text.rstrip() + f"\n{entry}"

    memory_file.write_text(text, encoding="utf-8")
    return f"已记住：{entry.strip()}"
