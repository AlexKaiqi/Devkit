"""
LocalAgent — self-hosted agent runtime.

Uses the openai SDK directly for LLM inference with tool calling.
Implements the AgentBackend protocol so bot.py / server.py can swap
in with zero interface changes.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from openai import AsyncOpenAI

from tools import discover_tools, get_schemas, get_skill_context, run_tool, set_context

log = logging.getLogger("local-agent")

MAX_HISTORY = 40
MAX_TOOL_ROUNDS = 15
DEFAULT_REPO_ROOT = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[2])))
DEFAULT_WORKSPACE_DIR = "implementation/assets/persona"

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

        # Task graph (initialised lazily via init_task_graph)
        self._task_graph_store: Any = None
        self._task_orchestrator: Any = None

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
            self._sessions[key] = []
        return self._sessions[key]

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

        try:
            while True:
                tool_round += 1
                if tool_round > MAX_TOOL_ROUNDS:
                    yield {"type": "error", "content": "Too many tool-calling rounds"}
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

                api_messages.extend(messages)

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

                if not tool_calls_map:
                    messages.append({"role": "assistant", "content": assistant_content})
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

                for tc in sorted_calls:
                    yield {"type": "tool", "name": tc["name"], "status": "running", "id": tc["id"]}

                async def _run_one(tc: dict) -> tuple[str, str, str, int]:
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    log.info("Tool call: %s(%s)", tc["name"], json.dumps(args, ensure_ascii=False)[:200])
                    t0 = time.monotonic()
                    result = await run_tool(tc["name"], args, session_key=session_key)
                    elapsed = round((time.monotonic() - t0) * 1000)
                    log.info("Tool %s completed in %dms, result=%d chars", tc["name"], elapsed, len(result))
                    return tc["id"], tc["name"], result, elapsed

                results = await asyncio.gather(*[_run_one(tc) for tc in sorted_calls])

                for tool_id, name, result, _ in results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": result,
                    })
                    yield {"type": "tool", "name": name, "status": "done", "id": tool_id}

        except Exception as e:
            log.error("Agent error: %s", e, exc_info=True)
            yield {"type": "error", "content": str(e)}
            return

        yield {"type": "done", "full_text": full_text}
