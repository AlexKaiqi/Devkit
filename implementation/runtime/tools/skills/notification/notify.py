"""notify tool — 并发双渠道推送（Telegram + Web Push）。"""

import asyncio
import logging
import os
from pathlib import Path

from tools import tool

log = logging.getLogger("notify")

_NOTIFY_SH = str(Path(__file__).resolve().parents[3] / "ops/scripts/notify.sh")
_VOICE_CHAT_PORT = int(os.environ.get("VOICE_CHAT_PORT", "3001"))


@tool(
    name="notify",
    description=(
        "Send an instant push notification to the user via Telegram and Web Push. "
        "Use for: task completion reports, alerts, async results, or anything the user should know right away. "
        "urgent=true bypasses quiet hours (23:00-08:00 CST)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Notification message (Markdown supported)"},
            "urgent": {"type": "boolean", "description": "Bypass quiet hours (default false)"},
        },
        "required": ["message"],
    },
)
async def handle(args: dict, ctx) -> str:
    message = args.get("message", "").strip()
    urgent = args.get("urgent", False)

    if not message:
        return "[error] message is required"

    results = await asyncio.gather(
        _send_telegram(message, urgent),
        _send_web_push(message),
        return_exceptions=True,
    )

    tg_result, wp_result = results
    parts = []

    if isinstance(tg_result, Exception):
        parts.append(f"Telegram 失败: {tg_result}")
    else:
        parts.append(tg_result)

    if isinstance(wp_result, Exception):
        log.warning("Web Push failed: %s", wp_result)
    elif wp_result:
        parts.append(wp_result)

    return " | ".join(parts)


async def _send_telegram(message: str, urgent: bool) -> str:
    cmd = [_NOTIFY_SH]
    if urgent:
        cmd.append("--urgent")
    cmd.append(message)

    env = {**os.environ}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        result = out.decode(errors="replace").strip()
        if proc.returncode == 0:
            return f"通知已发送: {message[:60]}{'...' if len(message) > 60 else ''}"
        return f"[error] notify: {result}"
    except Exception as e:
        return f"[error] notify: {e}"


async def _send_web_push(message: str) -> str | None:
    import aiohttp

    url = f"http://localhost:{_VOICE_CHAT_PORT}/api/push/send"
    payload = {"title": "风铃", "body": message}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    sent = data.get("sent", 0)
                    if sent > 0:
                        return f"Web Push 已推送 {sent} 端"
        return None
    except Exception as e:
        log.warning("Web Push delivery failed: %s", e)
        return None
