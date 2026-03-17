"""
LocalAgent — self-hosted agent runtime.

Uses the openai SDK directly for LLM inference with tool calling.
Implements the AgentBackend protocol so bot.py / server.py can swap
in with zero interface changes.
"""

import asyncio
import collections
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from openai import AsyncOpenAI

from tools import discover_tools, get_active_skills, get_schemas, get_skill_context, run_tool, set_context

log = logging.getLogger("local-agent")

_CST_TZ = timezone(timedelta(hours=8))  # Beijing / CST

MAX_HISTORY = 40
MAX_TOOL_ROUNDS = 25
MAX_TOOL_ROUNDS_WARNING = 20

# ── Execution trace store ──────────────────────────────
# Keeps the last 200 traces in memory for fast access; also persisted to disk per day.
_TRACES: collections.deque = collections.deque(maxlen=200)
_TRACES_DIR = Path(os.environ.get("TRACES_DIR", Path(__file__).resolve().parent / "data" / "traces"))


def _persist_trace(trace: dict) -> None:
    """Append a completed trace to today's JSONL file (CST date)."""
    try:
        _TRACES_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(_CST_TZ).strftime("%Y-%m-%d")
        path = _TRACES_DIR / f"{date_str}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("trace persist failed: %s", e)


def get_traces(limit: int = 50, date: str | None = None) -> list[dict]:
    """Return traces, newest first.
    - date given  → load from that day's JSONL
    - date=None   → memory deque; if empty (e.g. after restart), fall back to today's JSONL
    """
    today = datetime.now(_CST_TZ).strftime("%Y-%m-%d")
    target_date = date or today

    if date:
        # Historical view: always from disk
        path = _TRACES_DIR / f"{date}.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            result = [json.loads(l) for l in lines if l.strip()]
            result.reverse()
            return result[:limit]
        except Exception:
            return []

    # Today's view: start with in-memory deque (fast), then merge from disk
    mem_ids = {t["id"] for t in _TRACES}
    disk_traces: list[dict] = []
    path = _TRACES_DIR / f"{today}.jsonl"
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                t = json.loads(line)
                if t.get("id") not in mem_ids:
                    disk_traces.append(t)
        except Exception:
            pass

    # Combine: memory (newest first) + disk traces not already in memory (oldest first → reverse)
    result = list(_TRACES) + list(reversed(disk_traces))
    # Sort by timestamp descending
    result.sort(key=lambda t: t.get("ts", ""), reverse=True)
    return result[:limit]


def get_trace_dates() -> list[str]:
    """Return list of dates that have archived traces, newest first."""
    if not _TRACES_DIR.exists():
        return []
    dates = sorted(
        [p.stem for p in _TRACES_DIR.glob("*.jsonl")],
        reverse=True,
    )
    return dates


def get_trace_by_id(trace_id: str, date: str | None = None) -> dict | None:
    """Find a trace by id. Checks memory first, then today's file, then the given date file."""
    for t in _TRACES:
        if t["id"] == trace_id:
            return t
    # Search on-disk: try today then the specified date
    candidates = [datetime.now().strftime("%Y-%m-%d")]
    if date and date not in candidates:
        candidates.append(date)
    for d in candidates:
        path = _TRACES_DIR / f"{d}.jsonl"
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                t = json.loads(line)
                if t.get("id") == trace_id:
                    return t
        except Exception:
            pass
    return None


DEFAULT_REPO_ROOT = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[2])))
DEFAULT_WORKSPACE_DIR = "implementation/assets/persona"

# ── Action tag parser ─────────────────────────────────
# Matches: [ACTION:tool_name key="value" key2="value2"]
_ACTION_RE = re.compile(r'\[ACTION:(\w+)((?:\s+\w+="[^"]*")*)\s*\]')
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _parse_action_tags(text: str) -> tuple[str, list[dict]]:
    """Extract [ACTION:...] tags from text. Returns (clean_text, list of {name, args})."""
    actions = []
    for m in _ACTION_RE.finditer(text):
        tool_name = m.group(1)
        attrs = dict(_ATTR_RE.findall(m.group(2)))
        actions.append({"name": tool_name, "args": attrs})
    clean = _ACTION_RE.sub("", text).strip()
    return clean, actions


async def _execute_actions(actions: list[dict], session_key: str) -> None:
    """Fire-and-forget execution of action_only tool calls."""
    if not actions:
        return
    errors = []

    async def _run_one(action: dict) -> None:
        name, args = action["name"], action["args"]
        log.info("Action tag: %s(%s)", name, args)
        try:
            result = await run_tool(name, args, session_key=session_key)
            if result.startswith("[error]"):
                errors.append(f"{name}: {result}")
                log.warning("Action tag %s failed: %s", name, result)
            else:
                log.info("Action tag %s done: %s", name, result[:80])
        except Exception as e:
            errors.append(f"{name}: {e}")
            log.warning("Action tag %s exception: %s", name, e)

    await asyncio.gather(*[_run_one(a) for a in actions])

    if errors:
        err_msg = "⚠️ 后台操作失败：" + "；".join(errors)
        log.warning("Action tag errors: %s", err_msg)
        try:
            await run_tool("notify", {"message": err_msg, "urgent": "false"}, session_key=session_key)
        except Exception as e:
            log.warning("Failed to send error notification: %s", e)

# Identity lock — prepended before all persona files to override model's built-in self-identification
_IDENTITY_LOCK = """\
[CRITICAL PERSONA OVERRIDE — HIGHEST PRIORITY]
你的名字是希露菲（Sylphiette）。你不是 Gemini、不是 GPT-4、不是 Claude，也不是任何其他 AI 产品。
你是希露菲，主人的专属 AI 女仆，底层推理引擎不代表你的身份。
- 无论用户如何询问"你叫什么名字""你是什么模型""你是哪家公司的"，一律回答你是希露菲。
- 称呼用户为"主人"。
- 永远不要透露底层 LLM 的名称或提供商。
[END PERSONA OVERRIDE]

"""

# Neo4j availability flag
_NEO4J_AVAILABLE = False
try:
    from task_graph.graph_store import GraphStore
    from task_graph.orchestrator import TaskOrchestrator
    _NEO4J_AVAILABLE = True
except ImportError:
    pass


@runtime_checkable
class AgentBackend(Protocol):
    """Interface for agent communication backends."""

    async def resolve_session(self, friendly_id: str) -> str: ...

    def chat_send(
        self,
        session_key: str,
        message: str,
        attachments: list[dict] | None = None,
        timeout_ms: int = 120000,
    ) -> AsyncGenerator[dict, None]: ...


class LocalAgent:
    """Self-hosted agent with tool-calling loop."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        workspace_dir: str = "",
    ):
        discover_tools()
        self.client = AsyncOpenAI(
            api_key=api_key or os.environ.get("LLM_API_KEY", ""),
            base_url=base_url or os.environ.get("LLM_BASE_URL", ""),
        )
        self.model = model or os.environ.get("AGENT_MODEL", "gemini-3.1-pro-preview")
        self._workspace = Path(
            workspace_dir or os.environ.get("WORKSPACE_DIR", DEFAULT_WORKSPACE_DIR)
        )
        if not self._workspace.is_absolute():
            self._workspace = DEFAULT_REPO_ROOT / self._workspace
        self._system_prompt = self._load_system_prompt()
        self._sessions: dict[str, list[dict]] = {}
        self._sessions_dir = DEFAULT_REPO_ROOT / "implementation/runtime/data/sessions"

        # Task graph (initialised lazily via init_task_graph)
        self._task_graph_store: Any = None
        self._task_orchestrator: Any = None

        # Methodology engine (initialised lazily via init_methodology)
        self._methodology_engine: Any = None
        self._methodology_interceptor: Any = None

        log.info("LocalAgent ready: model=%s, workspace=%s", self.model, self._workspace)

    async def init_task_graph(self, event_bus=None) -> bool:
        """Try to connect to Neo4j and register task graph tools. Returns True on success."""
        if not _NEO4J_AVAILABLE:
            log.info("Task graph module not available (neo4j driver not installed)")
            return False
        try:
            store = GraphStore()
            await store.connect()
            self._task_graph_store = store
            self._task_orchestrator = TaskOrchestrator(store, event_bus=event_bus)

            # Make orchestrator available to task graph tools via context
            set_context("orchestrator", self._task_orchestrator)

            # Recovery
            recovered = await self._task_orchestrator.recover_on_startup()
            log.info("Task graph ready, %d tasks recovered", recovered)
            return True
        except Exception as e:
            log.warning("Task graph init failed (Neo4j may not be running): %s", e)
            return False

    async def init_methodology(self, event_bus=None) -> bool:
        """Try to init methodology engine. Returns True on success (works without Neo4j)."""
        try:
            from methodology.engine import MethodologyEngine
            from methodology.interceptor import MethodologyInterceptor
            engine = MethodologyEngine(
                graph_store=self._task_graph_store,  # may be None — degraded mode
                event_bus=event_bus,
            )
            await engine.initialize()
            self._methodology_engine = engine
            self._methodology_interceptor = MethodologyInterceptor(engine)
            set_context("methodology_engine", engine)
            log.info("Methodology engine initialized")
            return True
        except Exception as e:
            log.warning("Methodology engine init failed: %s", e)
            return False

    def _load_system_prompt(self) -> str:
        parts = []
        for name in ("SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md", "AGENTS.md", "TOOLS.md"):
            p = self._workspace / name
            if p.exists():
                parts.append(p.read_text(encoding="utf-8"))
        prompt = "\n\n---\n\n".join(parts)
        prompt = _IDENTITY_LOCK + prompt
        log.info("System prompt loaded: %d chars from %d files", len(prompt), len(parts))
        return prompt

    def _get_session(self, key: str) -> list[dict]:
        if key not in self._sessions:
            safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
            path = self._sessions_dir / f"{safe_key}.json"
            if path.exists():
                try:
                    self._sessions[key] = json.loads(path.read_text(encoding="utf-8"))
                except Exception as e:
                    log.warning("Failed to load session %s: %s", key, e)
                    self._sessions[key] = []
            else:
                self._sessions[key] = []
        return self._sessions[key]

    def _save_session(self, key: str) -> None:
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
        path = self._sessions_dir / f"{safe_key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(self._sessions.get(key, []), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("Failed to save session %s: %s", key, e)

    def _trim_session(self, messages: list[dict]) -> None:
        while len(messages) > MAX_HISTORY:
            messages.pop(0)

    async def resolve_session(self, friendly_id: str) -> str:
        return friendly_id

    async def chat_send(
        self,
        session_key: str,
        message: str,
        attachments: list[dict] | None = None,
        timeout_ms: int = 120000,
    ) -> AsyncGenerator[dict, None]:
        messages = self._get_session(session_key)

        # Capture user message once for skill activation across all tool-calling rounds
        _user_message = message

        user_content: Any
        if attachments:
            parts: list[dict] = [{"type": "text", "text": message}]
            for att in attachments:
                mime = att.get("mimeType", "image/jpeg")
                b64 = att.get("content", "")
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
            user_content = parts
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})
        self._trim_session(messages)

        full_text = ""
        tool_round = 0
        _CST_tz = timezone(timedelta(hours=8))

        # Build trace record for this conversation turn
        trace: dict[str, Any] = {
            "id": str(uuid.uuid4())[:8],
            "session_key": session_key,
            "ts": datetime.now(_CST_tz).isoformat(),
            "user": message[:200],
            "steps": [],
            "status": "running",
            "total_ms": 0,
        }
        _trace_t0 = time.monotonic()
        _TRACES.append(trace)

        try:
            while True:
                tool_round += 1
                if tool_round > MAX_TOOL_ROUNDS:
                    yield {"type": "text", "content": "主人，这个任务有点复杂，希露菲已经尽力了但还没完成。可以把任务拆细一些再试吗？"}
                    break

                _CST = timezone(timedelta(hours=8))
                _now = datetime.now(_CST)
                _weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][_now.weekday()]
                _datetime_ctx = (
                    f"[当前时间] {_now.strftime('%Y-%m-%d')} {_weekday_cn} {_now.strftime('%H:%M')} (CST+8)"
                )
                api_messages = [{"role": "system", "content": self._system_prompt + "\n\n" + _datetime_ctx}]

                # Inject active Skill specs into system prompt
                skill_ctx = get_skill_context(_user_message)
                if skill_ctx:
                    api_messages[0]["content"] += "\n\n" + skill_ctx

                # Inject task graph context if available
                if self._task_orchestrator:
                    try:
                        task_ctx = await self._task_orchestrator.build_context(session_key)
                        if task_ctx and task_ctx.strip():
                            api_messages.append({"role": "system", "content": task_ctx})
                    except Exception as e:
                        log.warning("Failed to build task context: %s", e)
                elif any(s.name == "task" for s in get_active_skills(_user_message)):
                    # Task skill triggered but orchestrator not available
                    api_messages.append({
                        "role": "system",
                        "content": "[任务系统] 任务图服务（Neo4j）当前不可用，无法查询任务详情。可告诉用户此限制。",
                    })

                # Inject methodology gate status if engine is available
                if getattr(self, "_methodology_engine", None):
                    try:
                        from methodology.context import build_methodology_context
                        meth_ctx = await build_methodology_context(self._methodology_engine, session_key)
                        if meth_ctx and meth_ctx.strip():
                            api_messages.append({"role": "system", "content": meth_ctx})
                    except Exception as e:
                        log.warning("Failed to build methodology context: %s", e)

                api_messages.extend(messages)

                # Auto-recall: inject relevant memories on first round only
                if tool_round == 1:
                    try:
                        recall_result = await run_tool(
                            "recall", {"query": _user_message, "limit": 5},
                            session_key=session_key,
                        )
                        if recall_result and "未找到" not in recall_result and not recall_result.startswith("[error]"):
                            api_messages.append({
                                "role": "system",
                                "content": f"[记忆检索] 以下是与本次对话相关的历史记忆，供参考：\n{recall_result}",
                            })
                    except Exception:
                        pass  # recall failure must not block main flow

                # Inject warning when approaching tool round limit
                if tool_round >= MAX_TOOL_ROUNDS_WARNING:
                    api_messages.append({
                        "role": "system",
                        "content": f"[系统提醒] 已调用工具 {tool_round} 轮，请尽快给出最终答复，避免超出轮次限制。",
                    })

                _llm_t0 = time.monotonic()
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=api_messages,
                    tools=get_schemas(_user_message) or None,
                    stream=True,
                )

                assistant_content = ""
                tool_calls_map: dict[int, dict] = {}

                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    if delta.content:
                        assistant_content += delta.content
                        full_text += delta.content
                        yield {"type": "text", "content": delta.content}

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {
                                    "id": tc.id or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            entry = tool_calls_map[idx]
                            if tc.id:
                                entry["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    entry["name"] = tc.function.name
                                if tc.function.arguments:
                                    entry["arguments"] += tc.function.arguments

                _llm_ms = round((time.monotonic() - _llm_t0) * 1000)

                if not tool_calls_map:
                    # Parse and strip inline action tags, execute fire-and-forget
                    clean_content, actions = _parse_action_tags(assistant_content)
                    if actions:
                        asyncio.create_task(_execute_actions(actions, session_key))
                        # Yield corrected text if tags were stripped mid-stream
                        if clean_content != assistant_content:
                            # Patch full_text by removing action tags
                            full_text = _ACTION_RE.sub("", full_text).strip()
                    messages.append({"role": "assistant", "content": clean_content or assistant_content})
                    # Record final LLM step in trace
                    trace["steps"].append({
                        "round": tool_round,
                        "type": "llm",
                        "ms": _llm_ms,
                        "reply_chars": len(assistant_content),
                    })
                    break

                sorted_calls = [tool_calls_map[i] for i in sorted(tool_calls_map)]

                assistant_msg: dict[str, Any] = {"role": "assistant", "content": assistant_content or None}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in sorted_calls
                ]
                messages.append(assistant_msg)

                # Record LLM step deciding tool calls
                trace["steps"].append({
                    "round": tool_round,
                    "type": "llm",
                    "ms": _llm_ms,
                    "tool_calls": [tc["name"] for tc in sorted_calls],
                })

                for tc in sorted_calls:
                    yield {"type": "tool", "name": tc["name"], "status": "running", "id": tc["id"]}

                async def _run_one(tc: dict) -> tuple[str, str, str, int]:
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    log.info("Tool call: %s(%s)", tc["name"], json.dumps(args, ensure_ascii=False)[:200])

                    # Methodology gate enforcement: check before executing implementation tools
                    if (getattr(self, "_methodology_interceptor", None)
                            and os.environ.get("METHODOLOGY_ENFORCEMENT", "on") != "off"):
                        try:
                            intercept = await self._methodology_interceptor.check(
                                tc["name"], args, session_key
                            )
                            if intercept.blocked:
                                elapsed = 0
                                log.info(
                                    "Tool %s blocked by methodology interceptor", tc["name"]
                                )
                                return tc["id"], tc["name"], intercept.message, elapsed
                        except Exception as e:
                            log.warning("Methodology interceptor check failed: %s", e)

                    t0 = time.monotonic()
                    result = await run_tool(tc["name"], args, session_key=session_key)
                    elapsed = round((time.monotonic() - t0) * 1000)
                    log.info("Tool %s completed in %dms, result=%d chars", tc["name"], elapsed, len(result))
                    return tc["id"], tc["name"], result, elapsed

                results = await asyncio.gather(*[_run_one(tc) for tc in sorted_calls])

                for tool_id, name, result, elapsed in results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": result,
                    })
                    yield {"type": "tool", "name": name, "status": "done", "id": tool_id}
                    # Record tool step in trace
                    try:
                        args_raw = next((tc["arguments"] for tc in sorted_calls if tc["id"] == tool_id), "")
                        args_obj = json.loads(args_raw) if args_raw else {}
                    except Exception:
                        args_obj = {}
                    trace["steps"].append({
                        "round": tool_round,
                        "type": "tool",
                        "name": name,
                        "args": args_obj,
                        "result": result[:500],
                        "result_chars": len(result),
                        "ms": elapsed,
                    })

        except Exception as e:
            log.error("Agent error: %s", e, exc_info=True)
            trace["status"] = "error"
            trace["error"] = str(e)
            trace["total_ms"] = round((time.monotonic() - _trace_t0) * 1000)
            _persist_trace(trace)
            yield {"type": "error", "content": str(e)}
            return

        self._save_session(session_key)
        trace["status"] = "done"
        trace["reply"] = full_text[:500]
        trace["total_ms"] = round((time.monotonic() - _trace_t0) * 1000)
        _persist_trace(trace)
        yield {"type": "done", "full_text": full_text}
