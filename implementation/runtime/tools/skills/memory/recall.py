"""recall tool — 全文搜索记忆文件，返回相关条目。"""

import os
import re
from pathlib import Path

from tools import tool

_PERSONA_DIR = Path(os.environ.get("WORKSPACE_DIR", "implementation/assets/persona"))
if not _PERSONA_DIR.is_absolute():
    _PERSONA_DIR = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[5]))) / _PERSONA_DIR

MAX_RESULTS = 20
MAX_CHARS = 4000


@tool(
    name="recall",
    description="在记忆文件（MEMORY.md + memory/ 日志）中搜索，返回相关条目。用于回答'之前说过…''我记得…'等问题。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词，支持多词（空格分隔为 AND 逻辑）"},
            "limit": {"type": "integer", "description": "最多返回条数（默认 10）"},
        },
        "required": ["query"],
    },
)
async def handle(args: dict, ctx) -> str:
    query = args["query"].strip()
    limit = min(int(args.get("limit", 10)), MAX_RESULTS)

    keywords = [k.lower() for k in query.split() if k]
    if not keywords:
        return "[error] 请提供搜索关键词"

    # 收集所有待搜索文件
    files: list[Path] = []
    memory_md = _PERSONA_DIR / "MEMORY.md"
    if memory_md.exists():
        files.append(memory_md)

    memory_dir = _PERSONA_DIR / "memory"
    if memory_dir.exists():
        # 最近 30 天的日志，倒序（新的在前）
        daily_logs = sorted(memory_dir.glob("*.md"), reverse=True)[:30]
        files.extend(daily_logs)

    hits: list[str] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in text.splitlines():
            line_lower = line.lower()
            if all(kw in line_lower for kw in keywords):
                hits.append(f"[{f.name}] {line.strip()}")
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break

    if not hits:
        return f"未找到包含「{query}」的记忆条目。"

    result = "\n".join(hits)
    if len(result) > MAX_CHARS:
        result = result[:MAX_CHARS] + "\n...(truncated)"
    return f"找到 {len(hits)} 条结果：\n\n{result}"
