"""list_files tool — list directory contents."""

import os
from pathlib import Path

from tools import tool

DEFAULT_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[3]))


@tool(
    name="list_files",
    description="List files and directories at a path. Shows names, types, and sizes. Use before read_file to explore unfamiliar directories.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to list (default: project root)"},
            "recursive": {"type": "boolean", "description": "Recursively list subdirectories (default false)"},
            "max_depth": {"type": "integer", "description": "Max recursion depth when recursive=true (default 2)"},
        },
        "required": [],
    },
)
async def handle(args: dict, ctx) -> str:
    path = args.get("path", "") or DEFAULT_WORKDIR
    recursive = args.get("recursive", False)
    max_depth = args.get("max_depth", 2)

    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(DEFAULT_WORKDIR) / p

        if not p.exists():
            return f"[error] Path not found: {p}"
        if p.is_file():
            stat = p.stat()
            return f"{p.name}  ({stat.st_size} bytes)"

        lines = []

        def _list(dirp: Path, depth: int, prefix: str) -> None:
            if recursive and depth > max_depth:
                return
            entries = sorted(dirp.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith(".") and depth > 0:
                    continue  # hide dotfiles in sub-levels
                if entry.is_dir():
                    lines.append(f"{prefix}{entry.name}/")
                    if recursive:
                        _list(entry, depth + 1, prefix + "  ")
                else:
                    size = entry.stat().st_size
                    size_str = f"{size}B" if size < 1024 else f"{size // 1024}KB"
                    lines.append(f"{prefix}{entry.name}  ({size_str})")

        _list(p, 0, "")
        if not lines:
            return "(empty directory)"
        result = f"{p}/\n" + "\n".join(lines)
        if len(result) > 20_000:
            result = result[:20_000] + "\n...(truncated)"
        return result
    except Exception as e:
        return f"[error] list_files: {e}"
