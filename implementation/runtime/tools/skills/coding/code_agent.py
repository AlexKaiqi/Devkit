"""code_agent tool — 通过 Claude Code CLI 执行编码任务。

spawn `claude-internal -p` 进程，通过 OpenRouter proxy 调用 Claude 模型，
解析 JSON 结果返回给风铃聊天。
"""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path

from tools import tool

log = logging.getLogger("code-agent")

_WORKDIR = os.environ.get("DEVKIT_DIR", str(Path(__file__).resolve().parents[5]))
_MAX_OUTPUT = 16_000
_TIMEOUT = 300  # 5 分钟
_MAX_BUDGET = "2.00"  # 单次预算上限（大文件读取 token 开销高）

# claude-internal CLI 查找：优先环境变量，再 PATH，再 nvm 常见位置
_CLAUDE_CLI = os.environ.get("CLAUDE_CODE_CLI", "")

MODEL_MAP = {
    "sonnet": "claude-sonnet-4-5",
    "haiku": "claude-haiku-4-5",
    "opus": "claude-opus-4-5",
}
DEFAULT_MODEL = "sonnet"


def _find_claude_cli() -> str:
    """Find claude-internal CLI binary."""
    if _CLAUDE_CLI:
        return _CLAUDE_CLI
    # Try PATH
    found = shutil.which("claude-internal")
    if found:
        return found
    # Common nvm location
    nvm_dir = os.environ.get("NVM_DIR", os.path.expanduser("~/.nvm"))
    for candidate in Path(nvm_dir).glob("versions/node/*/bin/claude-internal"):
        return str(candidate)
    return "claude-internal"  # fallback, hope it's in PATH


@tool(
    name="code_agent",
    description=(
        "启动 Claude Code CLI 执行编码任务。"
        "适合：实现新功能、修复 bug、重构代码、生成脚本、代码 review。"
        "Claude 有独立 context，直接读写文件和执行命令，完成后返回摘要报告。"
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
            "model": {
                "type": "string",
                "description": "模型: sonnet(默认) / haiku / opus",
            },
        },
        "required": ["prompt"],
    },
)
async def handle(args: dict, ctx) -> str:
    prompt = args["prompt"].strip()
    workdir = args.get("workdir") or _WORKDIR
    model_key = args.get("model", DEFAULT_MODEL).lower().strip()
    model_name = MODEL_MAP.get(model_key, MODEL_MAP[DEFAULT_MODEL])

    proxy_port = os.environ.get("CLAUDE_CODE_PROXY_PORT", "9999")
    cli_path = _find_claude_cli()

    # 构建命令
    cmd = [
        cli_path,
        "-p", prompt,
        "--model", model_name,
        "--output-format", "json",
        "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep",
        "--max-budget-usd", _MAX_BUDGET,
        "--no-session-persistence",
    ]

    # 获取方法论上下文并注入 CLI
    methodology_prompt = ""
    try:
        engine = ctx.get("methodology_engine") if ctx and hasattr(ctx, "get") else None
        if engine:
            from methodology.context import build_methodology_context
            session_key = getattr(ctx, "session_key", None) or "default"
            methodology_prompt = await build_methodology_context(engine, session_key)
    except Exception:
        pass  # 降级：无方法论上下文也可以运行

    if methodology_prompt:
        cmd.extend(["--append-system-prompt", methodology_prompt])

    # 构建环境变量：继承当前环境 + 覆盖关键项
    merged_env = os.environ.copy()
    merged_env.update({
        "ANTHROPIC_API_KEY": "proxy-handles-auth",
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{proxy_port}",
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    })
    # 防止嵌套检测
    merged_env.pop("CLAUDE_CODE", None)
    merged_env.pop("CLAUDECODE", None)

    log.info(
        "code_agent: cli=%s model=%s workdir=%s",
        cli_path, model_name, workdir,
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
            cwd=workdir,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_TIMEOUT
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return "[error] code_agent 超时（5分钟），任务可能过于复杂，建议拆分为子任务。"
    except FileNotFoundError:
        return (
            f"[error] 找不到 claude-internal CLI: {cli_path}\n"
            "请确认已安装 Claude Code CLI 并在 PATH 中。"
        )
    except Exception as e:
        log.error("code_agent unexpected error: %s", e, exc_info=True)
        return f"[error] code_agent 启动失败: {e}"

    # 非零退出码
    if proc.returncode != 0:
        err_text = stderr.decode("utf-8", errors="replace").strip()
        if not err_text:
            err_text = stdout.decode("utf-8", errors="replace").strip()
        err_text = err_text[:2000]  # 截断错误信息
        return f"[error] code_agent 退出码 {proc.returncode}\n{err_text}"

    # 解析 JSON 输出
    raw = stdout.decode("utf-8", errors="replace").strip()
    try:
        result = json.loads(raw)
        subtype = result.get("subtype", "")
        text = result.get("result", "")
        cost = result.get("cost_usd", 0) or result.get("total_cost_usd", 0) or 0
        duration = result.get("duration_ms", 0) or 0
        duration_s = duration / 1000 if duration else 0

        # 处理 CLI 错误 subtype
        if not text and subtype == "error_max_budget_usd":
            text = (
                f"[error] 预算耗尽（${cost:.2f}），任务在执行中被截断。"
                "大文件读取消耗大量 token，建议：\n"
                "1. 缩小任务范围，指定具体文件和行号\n"
                "2. 将任务拆分为多个小步骤"
            )
        elif not text and subtype and subtype.startswith("error"):
            text = f"[error] Claude Code 异常退出: {subtype}"
    except (json.JSONDecodeError, KeyError):
        # 非 JSON 输出，直接返回原文
        text = raw
        cost = 0
        duration_s = 0

    if not text:
        text = "(Claude Code 无输出)"

    if len(text) > _MAX_OUTPUT:
        text = text[:_MAX_OUTPUT] + f"\n...(截断，共 {len(text)} 字符)"

    # 格式化结果
    footer_parts = []
    if cost:
        footer_parts.append(f"💰 ${cost:.4f}")
    if duration_s:
        footer_parts.append(f"⏱ {duration_s:.1f}s")
    footer = " | ".join(footer_parts)

    if footer:
        return f"{text}\n\n---\n{footer}"
    return text
