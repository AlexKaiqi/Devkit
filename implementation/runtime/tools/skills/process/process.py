"""process tools — background process lifecycle management."""

import asyncio
import collections
import logging
import os
import time
from pathlib import Path

from tools import tool

log = logging.getLogger("process")

DEFAULT_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[4]))

# ── In-memory process registry ───────────────────────────────────────────────
# pid → ProcessEntry (dict with keys: pid, label, command, started_at, state, returncode, log_lines)

_MAX_LOG_LINES = 2000

class _ProcessEntry:
    __slots__ = ("pid", "label", "command", "started_at", "state", "returncode", "log_deque", "_proc")

    def __init__(self, pid: int, label: str, command: str, proc: asyncio.subprocess.Process):
        self.pid = pid
        self.label = label
        self.command = command
        self.started_at = time.time()
        self.state = "running"
        self.returncode: int | None = None
        self.log_deque: collections.deque = collections.deque(maxlen=_MAX_LOG_LINES)
        self._proc = proc

    def to_dict(self) -> dict:
        elapsed = round(time.time() - self.started_at)
        return {
            "pid": self.pid,
            "label": self.label,
            "command": self.command,
            "state": self.state,
            "returncode": self.returncode,
            "elapsed_sec": elapsed,
            "log_lines": len(self.log_deque),
        }


_REGISTRY: dict[int, _ProcessEntry] = {}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _stream_output(entry: _ProcessEntry) -> None:
    """Drain stdout+stderr into the entry's log deque; update state on exit."""
    proc = entry._proc
    assert proc.stdout is not None

    async def _read():
        while True:
            line = await proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                break
            entry.log_deque.append(line.decode(errors="replace").rstrip("\n"))

    try:
        await _read()
        returncode = await proc.wait()
        entry.returncode = returncode
        entry.state = "done" if returncode == 0 else "failed"
        log.info("Process pid=%d (%s) finished: rc=%d", entry.pid, entry.label, returncode)
    except Exception as e:
        entry.state = "error"
        log.warning("Process pid=%d stream error: %s", entry.pid, e)


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool(
    name="process_start",
    description=(
        "在后台启动一个 shell 命令，立即返回 pid。适合耗时脚本、编译、数据处理等长时间任务。"
        "完成后可用 process_log 查看输出，process_wait 等待结果。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要后台执行的 shell 命令"},
            "label": {"type": "string", "description": "便于识别的任务标签（可选）"},
            "workdir": {"type": "string", "description": "工作目录（默认项目根目录）"},
        },
        "required": ["command"],
    },
)
async def process_start(args: dict, ctx) -> str:
    command = args["command"].strip()
    label = args.get("label", command[:40]).strip()
    cwd = args.get("workdir", "") or DEFAULT_WORKDIR

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
            env={**os.environ},
        )
    except Exception as e:
        return f"[error] 启动失败: {e}"

    pid = proc.pid
    entry = _ProcessEntry(pid=pid, label=label, command=command, proc=proc)
    _REGISTRY[pid] = entry

    # Start background draining task
    asyncio.create_task(_stream_output(entry))

    log.info("process_start pid=%d label=%r cmd=%r", pid, label, command[:80])
    return f"已在后台启动: pid={pid}，标签={label!r}"


@tool(
    name="process_list",
    description="列出所有后台进程及其状态（running/done/failed）。",
    parameters={"type": "object", "properties": {}},
)
async def process_list(args: dict, ctx) -> str:
    if not _REGISTRY:
        return "当前没有后台进程。"

    lines = [f"{'PID':>7}  {'状态':8}  {'耗时':>6}  标签"]
    lines.append("-" * 50)
    for entry in sorted(_REGISTRY.values(), key=lambda e: e.started_at):
        d = entry.to_dict()
        elapsed = d["elapsed_sec"]
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        human = (f"{h}h" if h else "") + (f"{m}m" if m else "") + f"{s}s"
        state_icon = {"running": "🔄", "done": "✅", "failed": "❌", "error": "⚠️"}.get(d["state"], d["state"])
        rc = f" (rc={d['returncode']})" if d["returncode"] is not None else ""
        lines.append(f"{d['pid']:>7}  {state_icon + ' ' + d['state']:9}  {human:>6}  {d['label']}{rc}")

    return "\n".join(lines)


@tool(
    name="process_log",
    description="查看后台进程的输出日志（最新 N 行）。",
    parameters={
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "description": "进程 PID"},
            "lines": {"type": "integer", "description": "返回最新行数（默认 50）"},
        },
        "required": ["pid"],
    },
)
async def process_log(args: dict, ctx) -> str:
    pid = int(args["pid"])
    n = int(args.get("lines", 50))

    entry = _REGISTRY.get(pid)
    if not entry:
        return f"[error] 未找到 pid={pid} 的进程"

    log_lines = list(entry.log_deque)[-n:]
    d = entry.to_dict()
    header = f"[pid={pid} | {d['state']} | 共 {d['log_lines']} 行日志，显示最新 {len(log_lines)} 行]"
    if not log_lines:
        return header + "\n(暂无输出)"
    return header + "\n" + "\n".join(log_lines)


@tool(
    name="process_kill",
    description="终止后台进程。",
    parameters={
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "description": "要终止的进程 PID"},
        },
        "required": ["pid"],
    },
)
async def process_kill(args: dict, ctx) -> str:
    pid = int(args["pid"])
    entry = _REGISTRY.get(pid)
    if not entry:
        return f"[error] 未找到 pid={pid}"

    if entry.state != "running":
        return f"进程 pid={pid} 已处于 {entry.state} 状态，无需终止。"

    try:
        entry._proc.kill()
        await asyncio.wait_for(entry._proc.wait(), timeout=5)
    except Exception as e:
        log.warning("kill pid=%d error: %s", pid, e)

    entry.state = "killed"
    log.info("Process pid=%d killed", pid)
    return f"已终止进程 pid={pid}（{entry.label!r}）"


@tool(
    name="process_wait",
    description="等待后台进程完成并返回最终输出（适合等待编译/脚本结果）。",
    parameters={
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "description": "进程 PID"},
            "timeout": {"type": "number", "description": "最长等待秒数（默认 60）"},
            "tail_lines": {"type": "integer", "description": "返回最后 N 行（默认 30）"},
        },
        "required": ["pid"],
    },
)
async def process_wait(args: dict, ctx) -> str:
    pid = int(args["pid"])
    timeout = float(args.get("timeout", 60))
    tail = int(args.get("tail_lines", 30))

    entry = _REGISTRY.get(pid)
    if not entry:
        return f"[error] 未找到 pid={pid}"

    if entry.state != "running":
        log_lines = list(entry.log_deque)[-tail:]
        d = entry.to_dict()
        return f"进程已结束：{d['state']}（rc={d['returncode']}）\n" + "\n".join(log_lines)

    # Poll until done or timeout
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        if entry.state != "running":
            break

    d = entry.to_dict()
    log_lines = list(entry.log_deque)[-tail:]
    status = f"进程 pid={pid}（{entry.label!r}）：{d['state']}（rc={d['returncode']}，耗时 {d['elapsed_sec']}s）"
    if entry.state == "running":
        status += f"\n（等待超时 {timeout}s，进程仍在运行，可稍后再查）"
    return status + "\n" + "\n".join(log_lines)
