"""
LocalAgent — self-hosted agent runtime.

Uses the openai SDK directly for LLM inference with tool calling.
Implements the AgentBackend protocol so bot.py / server.py can swap
in with zero interface changes.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from openai import AsyncOpenAI

from tools import TOOL_SCHEMAS, run_tool

log = logging.getLogger("local-agent")

MAX_HISTORY = 40
MAX_TOOL_ROUNDS = 15
DEFAULT_REPO_ROOT = Path(os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[2])))
DEFAULT_WORKSPACE_DIR = "implementation/assets/persona"


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
        log.info("LocalAgent ready: model=%s, workspace=%s", self.model, self._workspace)

    def _load_system_prompt(self) -> str:
        parts = []
        for name in ("SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md", "AGENTS.md", "TOOLS.md"):
            p = self._workspace / name
            if p.exists():
                parts.append(p.read_text(encoding="utf-8"))
        prompt = "\n\n---\n\n".join(parts)
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

                api_messages = [{"role": "system", "content": self._system_prompt}] + messages

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=api_messages,
                    tools=TOOL_SCHEMAS if TOOL_SCHEMAS else None,
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
                    name = tc["name"]
                    yield {"type": "tool", "name": name, "status": "running", "id": tc["id"]}

                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}

                    log.info("Tool call: %s(%s)", name, json.dumps(args, ensure_ascii=False)[:200])
                    t0 = time.monotonic()
                    result = await run_tool(name, args)
                    elapsed = round((time.monotonic() - t0) * 1000)
                    log.info("Tool %s completed in %dms, result=%d chars", name, elapsed, len(result))

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                    yield {"type": "tool", "name": name, "status": "done", "id": tc["id"]}

        except Exception as e:
            log.error("Agent error: %s", e, exc_info=True)
            yield {"type": "error", "content": str(e)}
            return

        yield {"type": "done", "full_text": full_text}
