"""write_file tool — write content to a file."""

import os
from pathlib import Path

from tools import tool

DEFAULT_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[3]))


@tool(
    name="write_file",
    description="Write content to a file (creates parent directories if needed).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
            "content": {"type": "string", "description": "Content to write"},
            "confirmed": {"type": "boolean", "description": "用户已确认此操作（受控操作需要）"},
        },
        "required": ["path", "content"],
    },
)
async def handle(args: dict, ctx) -> str:
    path = args["path"]
    content = args["content"]
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(DEFAULT_WORKDIR) / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK, wrote {len(content)} bytes to {p}"
    except Exception as e:
        return f"[error] {e}"
