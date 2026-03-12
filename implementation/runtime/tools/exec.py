"""exec tool — run a shell command and return stdout+stderr."""

import asyncio
import os
from pathlib import Path

from tools import tool

DEFAULT_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[3]))
EXEC_TIMEOUT = 120


@tool(
    name="exec",
    description="Run a shell command and return stdout+stderr. Use for: git, curl, python, scripts (timer.sh, notify.sh, heartbeat.sh), mcporter, etc.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
            "workdir": {"type": "string", "description": "Working directory (default: project root)"},
            "confirmed": {"type": "boolean", "description": "用户已确认此操作（受控操作需要）"},
        },
        "required": ["command"],
    },
)
async def handle(args: dict, ctx) -> str:
    command = args["command"]
    cwd = args.get("workdir", "") or DEFAULT_WORKDIR
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
