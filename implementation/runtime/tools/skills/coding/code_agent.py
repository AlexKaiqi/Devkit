"""code_agent tool — 在进程内启动一个隔离的编程子代理。

子代理复用同一 LLM 客户端和工具注册表，但有：
- 独立 session（无主 agent 历史）
- 精简的编程专用 system prompt
- 只激活 system skill 工具（exec / read_file / write_file / list_files / search / fetch_url）
- 独立的 tool-calling 循环，最多 20 轮
"""

import json
import logging
import os
import time
from pathlib import Path

from openai import AsyncOpenAI

from tools import tool, run_tool, _REGISTRY

log = logging.getLogger("code-agent")

_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[5]))
_MAX_ROUNDS = 20
_MAX_OUTPUT = 16_000

_SYSTEM_PROMPT = """\
你是一个专注编程任务的 AI 子代理，在 {workdir} 目录下工作。

规范：
- 先用 list_files / read_file 理解现有代码，再动手
- 修改前确认文件路径和内容，避免覆盖无关代码
- 完成后输出简洁报告：做了什么、改了哪些文件、是否需要验证

只做被要求的事，不要引入额外改动。
"""

# 只允许 system skill 工具
_ALLOWED_TOOLS = {"exec", "read_file", "write_file", "list_files", "search", "fetch_url"}


def _get_coding_schemas() -> list[dict]:
    return [td.schema for name, td in _REGISTRY.items() if name in _ALLOWED_TOOLS]


@tool(
    name="code_agent",
    description=(
        "启动一个隔离的编程子代理执行编码任务。"
        "适合：实现新功能、修复 bug、重构代码、生成脚本、代码 review。"
        "子代理有独立 context，直接读写文件和执行命令，完成后返回摘要报告。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "完整的任务描述，包含：做什么、在哪个文件/目录、验收标准。越具体越好。",
            },
            "workdir": {
                "type": "string",
                "description": "工作目录（默认：项目根目录）",
            },
        },
        "required": ["prompt"],
    },
)
async def handle(args: dict, ctx) -> str:
    prompt = args["prompt"].strip()
    workdir = args.get("workdir") or _WORKDIR

    client = AsyncOpenAI(
        api_key=os.environ.get("LLM_API_KEY", ""),
        base_url=os.environ.get("LLM_BASE_URL", ""),
    )
    model = os.environ.get("AGENT_MODEL", "gemini-3.1-pro-preview")
    system = _SYSTEM_PROMPT.format(workdir=workdir)
    schemas = _get_coding_schemas()

    messages: list[dict] = [
        {"role": "user", "content": prompt},
    ]
    full_output = ""
    session_key = f"code_agent_{int(time.monotonic() * 1000)}"

    log.info("code_agent started: model=%s, tools=%s", model, [s["function"]["name"] for s in schemas])

    for round_n in range(1, _MAX_ROUNDS + 1):
        api_messages = [{"role": "system", "content": system}] + messages

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=api_messages,
                tools=schemas or None,
                stream=True,
            )
        except Exception as e:
            return f"[error] code_agent LLM call failed: {e}"

        assistant_text = ""
        tool_calls_map: dict[int, dict] = {}

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            if delta.content:
                assistant_text += delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                    entry = tool_calls_map[idx]
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            entry["name"] = tc.function.name
                        if tc.function.arguments:
                            entry["arguments"] += tc.function.arguments

        if assistant_text:
            full_output = assistant_text  # 最后一轮文本即最终报告

        if not tool_calls_map:
            messages.append({"role": "assistant", "content": assistant_text})
            break

        sorted_calls = [tool_calls_map[i] for i in sorted(tool_calls_map)]
        messages.append({
            "role": "assistant",
            "content": assistant_text or None,
            "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in sorted_calls
            ],
        })

        import asyncio as _asyncio

        async def _run_one(tc: dict) -> tuple[str, str, str]:
            try:
                tc_args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                tc_args = {}
            # 限制 exec 的 workdir 到子代理工作目录
            if tc["name"] == "exec" and "workdir" not in tc_args:
                tc_args["workdir"] = workdir
            log.info("code_agent tool: %s(%s)", tc["name"], str(tc_args)[:120])
            result = await run_tool(tc["name"], tc_args, session_key=session_key)
            return tc["id"], tc["name"], result

        results = await _asyncio.gather(*[_run_one(tc) for tc in sorted_calls])

        for tool_id, name, result in results:
            messages.append({"role": "tool", "tool_call_id": tool_id, "content": result})

    else:
        full_output = (full_output or "") + f"\n[警告] 已达到最大工具轮次 {_MAX_ROUNDS}，任务可能未完成"

    if len(full_output) > _MAX_OUTPUT:
        full_output = full_output[:_MAX_OUTPUT] + f"\n...(截断，共 {len(full_output)} 字符)"

    return full_output or "(子代理无输出)"
