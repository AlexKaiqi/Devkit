"""read_file tool — read a file and return its contents."""

import os
from pathlib import Path

from tools import tool

DEFAULT_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[3]))


@tool(
    name="read_file",
    description="Read a file and return its contents.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
        },
        "required": ["path"],
    },
)
async def handle(args: dict, ctx) -> str:
    path = args["path"]
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(DEFAULT_WORKDIR) / p
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 50_000:
            content = content[:50_000] + "\n...(truncated at 50KB)..."
        return content
    except Exception as e:
        return f"[error] {e}"
