"""
Tool definitions and execution engine for LocalAgent.
Each tool has a JSON Schema (OpenAI function-calling format) and an async handler.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import aiohttp

log = logging.getLogger("agent-tools")

DEFAULT_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).parent.parent))
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080")
EXEC_TIMEOUT = 120

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "exec",
            "description": "Run a shell command and return stdout+stderr. Use for: git, curl, python, scripts (timer.sh, notify.sh, heartbeat.sh), mcporter, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "workdir": {"type": "string", "description": "Working directory (default: project root)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates parent directories if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the web via SearXNG. Returns title + URL + snippet for each result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
]


async def _exec(command: str, workdir: str = "") -> str:
    cwd = workdir or DEFAULT_WORKDIR
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
            env={**os.environ, "PATH": os.environ.get("PATH", "")},
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=EXEC_TIMEOUT)
        output = stdout.decode(errors="replace")
        if len(output) > 50_000:
            output = output[:25_000] + "\n...(truncated)...\n" + output[-25_000:]
        prefix = f"[exit {proc.returncode}]\n" if proc.returncode else ""
        return prefix + output
    except asyncio.TimeoutError:
        proc.kill()
        return f"[error] Command timed out after {EXEC_TIMEOUT}s"
    except Exception as e:
        return f"[error] {e}"


async def _read_file(path: str) -> str:
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


async def _write_file(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(DEFAULT_WORKDIR) / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK, wrote {len(content)} bytes to {p}"
    except Exception as e:
        return f"[error] {e}"


async def _search(query: str, max_results: int = 5) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{SEARXNG_URL}/search",
                params={"q": query, "format": "json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
        results = data.get("results", [])[:max_results]
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '')}")
            lines.append(f"   {r.get('url', '')}")
            snippet = r.get("content", "")
            if snippet:
                lines.append(f"   {snippet[:200]}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"[error] Search failed: {e}"


_HANDLERS: dict[str, Any] = {
    "exec": _exec,
    "read_file": _read_file,
    "write_file": _write_file,
    "search": _search,
}


async def run_tool(name: str, arguments: dict) -> str:
    handler = _HANDLERS.get(name)
    if not handler:
        return f"[error] Unknown tool: {name}"
    try:
        return await handler(**arguments)
    except TypeError as e:
        return f"[error] Invalid arguments for {name}: {e}"
