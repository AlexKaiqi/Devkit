"""
Telegram Bot for 希露菲 — text + voice + image + video conversations.
Routes all chat through LocalAgent for full Agent capabilities.
"""

import asyncio
import base64
import io
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction
import aiohttp
from aiohttp import web

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))
from agent import AgentBackend, LocalAgent
from event_bus import EventBus, Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_utils import parse_response, extract_video_frames

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("tg-bot")

# ── Config ───────────────────────────────────────────

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

STT_PROXY = os.environ.get("STT_PROXY_URL", "http://localhost:8787")
DOUBAO_APPID = os.environ.get("DOUBAO_APPID", "")
DOUBAO_TOKEN = os.environ.get("DOUBAO_TOKEN", "")
DOUBAO_TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"
TTS_VOICE = os.environ.get("TTS_VOICE", "zh_female_tianmeixiaoyuan_moon_bigtts")
TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.25"))

# ── Agent ─────────────────────────────────────────────

agent = LocalAgent()

TIMER_API_PORT = int(os.environ.get("TIMER_API_PORT", "8789"))
VOICE_CHAT_PORT = int(os.environ.get("VOICE_CHAT_PORT", "3001"))

event_bus = EventBus(
    persist_path=Path(__file__).resolve().parents[2] / "runtime" / "data" / "timers.json"
)

# Bidirectional session <-> chat_id mapping
_session_keys: dict[int, str] = {}
_chat_ids: dict[str, int] = {}

_bot_instance = None

# ── Audit ────────────────────────────────────────────

AUDIT_DIR = Path(os.environ.get(
    "AUDIT_DIR",
    Path(__file__).resolve().parents[2] / "data" / "voice-audit",
))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
CST = timezone(timedelta(hours=8))


def audit(event: str, **kwargs):
    entry = {
        "ts": datetime.now(CST).isoformat(),
        "event": event,
        "channel": "telegram",
        **kwargs,
    }
    log.info("[audit] %s", {k: v for k, v in entry.items() if k != "ts"})
    try:
        path = AUDIT_DIR / f"{datetime.now(CST).strftime('%Y-%m-%d')}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("audit write failed: %s", e)


# ── Helpers ──────────────────────────────────────────

async def stt_transcribe(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    form = aiohttp.FormData()
    form.add_field("file", audio_bytes, filename=filename, content_type="audio/ogg")
    form.add_field("model", "whisper-1")
    form.add_field("language", "zh")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{STT_PROXY}/v1/audio/transcriptions", data=form
        ) as resp:
            result = await resp.json()
            return result.get("text", "").strip()


async def tts_synthesize(text: str, voice: str = "") -> bytes | None:
    voice = voice or TTS_VOICE
    payload = {
        "app": {
            "appid": DOUBAO_APPID,
            "token": "access_token",
            "cluster": "volcano_tts",
        },
        "user": {"uid": "telegram-bot"},
        "audio": {"voice_type": voice, "encoding": "mp3", "speed_ratio": TTS_SPEED},
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "operation": "query",
        },
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            DOUBAO_TTS_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer; {DOUBAO_TOKEN}",
            },
            json=payload,
        ) as resp:
            result = await resp.json()
            if result.get("code") != 3000:
                log.error("TTS failed: %s", result.get("message", ""))
                return None
            return base64.b64decode(result["data"])


def _bind_session(chat_id: int, session_key: str) -> None:
    _session_keys[chat_id] = session_key
    _chat_ids[session_key] = chat_id


def session_to_chat_id(session_key: str) -> int | None:
    if session_key in _chat_ids:
        return _chat_ids[session_key]
    # Try extracting chat_id from common session key patterns
    for prefix in ("tg-", "telegram-"):
        if session_key.startswith(prefix):
            try:
                return int(session_key[len(prefix):].split(":")[0])
            except ValueError:
                pass
        # e.g. agent:main:tg-6952177147 (cron-created session)
        if prefix in session_key:
            try:
                tail = session_key.split(prefix, 1)[-1]
                return int(tail.split(":")[0].strip())
            except (ValueError, IndexError):
                pass
    return None


async def _resolve_session(chat_id: int) -> str:
    if chat_id in _session_keys:
        return _session_keys[chat_id]
    sk = f"tg-{chat_id}"
    _bind_session(chat_id, sk)
    return sk


async def chat_via_agent(
    chat_id: int, user_msg: str, images: list[str] | None = None,
) -> str:
    """Send message through LocalAgent and collect full response."""
    session_key = await _resolve_session(chat_id)

    attachments = None
    if images:
        attachments = []
        for url in images:
            if url.startswith("data:"):
                header, b64data = url.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                attachments.append({"mimeType": mime, "content": b64data})

    audit("req", chat_id=chat_id, user=user_msg,
          images=len(images) if images else 0, source="local")

    t0 = time.monotonic()
    full_reply = ""
    try:
        async for evt in agent.chat_send(
            session_key, user_msg or "请看看这些内容", attachments=attachments,
        ):
            if evt["type"] == "text":
                full_reply += evt["content"]
            elif evt["type"] == "done":
                full_reply = evt.get("full_text", full_reply)
            elif evt["type"] == "error":
                full_reply = f"抱歉，出了点问题：{evt['content']}"
    except Exception as e:
        full_reply = f"抱歉，出了点问题：{e}"
        log.error("Agent chat error: %s", e)

    elapsed = round((time.monotonic() - t0) * 1000)
    audit("res", chat_id=chat_id, assistant=full_reply[:500], ms=elapsed, source="local")
    return full_reply


# ── Handlers ─────────────────────────────────────────

def is_allowed(update: Update) -> bool:
    if ALLOWED_CHAT_ID == 0:
        return True
    return update.effective_chat.id == ALLOWED_CHAT_ID


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "主人好，我是希露菲 🎀\n"
        "随时为您效劳，发文字、语音、图片或文档都可以。\n\n"
        "常用指令：\n"
        "/clear — 清空当前对话记忆\n"
        "/timers — 查看待触发提醒\n"
        "/help — 查看所有指令"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "🎐 希露菲指令列表\n\n"
        "/start — 开始对话\n"
        "/clear — 清空本次会话的对话历史\n"
        "/timers — 列出所有待触发的提醒\n"
        "/help — 显示本帮助\n\n"
        "支持：文字 · 语音 · 图片 · 视频 · 文档（PDF/TXT/MD）"
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    chat_id = update.effective_chat.id
    session_key = await _resolve_session(chat_id)
    # Clear in-memory session
    if session_key in agent._sessions:
        agent._sessions[session_key] = []
    # Clear session file on disk
    agent._save_session(session_key)
    audit("session_clear", chat_id=chat_id)
    await update.message.reply_text("✅ 对话记忆已清空，我们重新开始吧。")


async def cmd_timers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    timers = event_bus.list_timers()
    if not timers:
        await update.message.reply_text("当前没有待触发的提醒。")
        return
    lines = [f"⏰ 待触发提醒（共 {len(timers)} 条）：\n"]
    for t in timers:
        remaining = round(t.get("remaining_seconds", 0))
        h, rem = divmod(remaining, 3600)
        m, s = divmod(rem, 60)
        human = (f"{h}h" if h else "") + (f"{m}m" if m else "") + f"{s}s"
        msg = t.get("payload", {}).get("message", "（无内容）")
        lines.append(f"• {msg[:60]} — {human} 后触发")
    await update.message.reply_text("\n".join(lines))


async def _send_code_block(update: Update, lang: str, code: str):
    try:
        escaped = code.replace("\\", "\\\\").replace("`", "\\`")
        await update.message.reply_text(
            f"```{lang}\n{escaped}\n```", parse_mode="MarkdownV2",
        )
    except Exception:
        await update.message.reply_text(f"[{lang}]\n{code}")


TG_MAX_LEN = 4000  # Telegram 单条上限 4096，留点余量


def _split_message(text: str) -> list[str]:
    """Split long text into Telegram-safe chunks, preferring paragraph boundaries."""
    if len(text) <= TG_MAX_LEN:
        return [text]
    parts = []
    while text:
        if len(text) <= TG_MAX_LEN:
            parts.append(text)
            break
        # Try to split at a paragraph boundary
        cut = text.rfind("\n\n", 0, TG_MAX_LEN)
        if cut == -1:
            cut = text.rfind("\n", 0, TG_MAX_LEN)
        if cut == -1:
            cut = TG_MAX_LEN
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts


async def _send_typing(bot, chat_id: int) -> None:
    """Send a typing indicator (best-effort, non-blocking)."""
    try:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass





# Telegram 限流：每条消息约 1次/秒，每 chat 约 20次/分钟
_STREAM_FLUSH_CHARS = 20   # 累积多少字符刷新一次
_STREAM_FLUSH_SECS = 0.8   # 或距上次刷新超过多少秒


async def _stream_to_message(
    bot,
    chat_id: int,
    session_key: str,
    user_msg: str,
    prefix: str = "",
    attachments: list[dict] | None = None,
) -> str:
    """Stream agent response into a live-updating Telegram message. Returns full text."""
    # 发占位消息
    placeholder = await bot.send_message(chat_id=chat_id, text="…")
    msg_id = placeholder.message_id

    buffer = ""
    last_flush = time.monotonic()
    last_sent = "…"
    tool_status = ""  # 显示当前工具调用状态

    async def _flush(final: bool = False):
        nonlocal last_flush, last_sent
        display = prefix + buffer
        if tool_status and not final:
            display = display + f"\n\n_{tool_status}_" if display else f"_{tool_status}_"
        if not display:
            display = "…"
        if display == last_sent:
            return
        # Telegram 单条最大 4096 字符；中间更新只取前 TG_MAX_LEN
        truncated = display[:TG_MAX_LEN]
        if len(display) > TG_MAX_LEN and not final:
            truncated = truncated + "…"
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=truncated)
            last_sent = display
            last_flush = time.monotonic()
        except Exception as e:
            # 忽略 "message is not modified" 等无害错误
            if "not modified" not in str(e).lower():
                log.debug("edit_message_text error: %s", e)

    try:
        async for evt in agent.chat_send(
            session_key, user_msg or "请看看这些内容", attachments=attachments,
        ):
            if evt["type"] == "text":
                buffer += evt["content"]
                now = time.monotonic()
                if len(buffer) - len(last_sent.removeprefix(prefix)) >= _STREAM_FLUSH_CHARS \
                        or now - last_flush >= _STREAM_FLUSH_SECS:
                    await _flush()

            elif evt["type"] == "tool":
                name = evt.get("name", "")
                status = evt.get("status", "")
                if status == "running":
                    tool_status = f"调用工具 {name}…"
                else:
                    tool_status = ""
                await _flush()

            elif evt["type"] == "done":
                buffer = evt.get("full_text", buffer)
                tool_status = ""

            elif evt["type"] == "error":
                buffer = f"抱歉，出了点问题：{evt['content']}"
                tool_status = ""

        # Final flush: first chunk goes into placeholder, rest as new messages
        full_display = prefix + buffer
        chunks = _split_message(full_display)
        if chunks:
            first = chunks[0]
            if first != last_sent:
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=first)
                except Exception as e:
                    if "not modified" not in str(e).lower():
                        log.debug("final edit error: %s", e)
            for extra_chunk in chunks[1:]:
                await bot.send_message(chat_id=chat_id, text=extra_chunk)
        elif last_sent == "…":
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="（无回复）")

    except Exception as e:
        log.error("Stream error: %s", e)
        buffer = f"抱歉，出了点问题：{e}"
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=buffer[:TG_MAX_LEN])
        except Exception:
            pass

    return buffer


async def _reply_text_task(bot, chat_id: int, user_msg: str):
    """Background: stream response into a live-updating message."""
    await _reply_text_task_with_attachments(bot, chat_id, user_msg, None)


async def _reply_text_task_with_attachments(
    bot, chat_id: int, user_msg: str, attachments: list[dict] | None
):
    """Background: stream response, optionally with image/file attachments."""
    session_key = await _resolve_session(chat_id)
    audit("req", chat_id=chat_id, user=user_msg, source="telegram-text",
          has_attachments=bool(attachments))
    t0 = time.monotonic()

    await _send_typing(bot, chat_id)

    try:
        full_reply = await _stream_to_message(
            bot, chat_id, session_key, user_msg, attachments=attachments,
        )
        elapsed = round((time.monotonic() - t0) * 1000)
        audit("res", chat_id=chat_id, assistant=full_reply[:500], ms=elapsed)

        # 发送代码块附件
        parsed = parse_response(full_reply)
        for att in parsed["attachments"]:
            try:
                escaped = att["content"].replace("\\", "\\\\").replace("`", "\\`")
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"```{att['language']}\n{escaped}\n```",
                    parse_mode="MarkdownV2",
                )
            except Exception:
                await bot.send_message(chat_id=chat_id, text=f"[{att['language']}]\n{att['content']}")
    except Exception as e:
        log.error("Background reply failed: %s", e)
        try:
            await bot.send_message(chat_id=chat_id, text=f"抱歉，出了点问题：{e}")
        except Exception:
            pass


async def _reply_voice_task(bot, chat_id: int, user_text: str):
    """Background: stream response, then send TTS audio."""
    session_key = await _resolve_session(chat_id)
    prefix = f"🎤 {user_text}\n\n"
    audit("req", chat_id=chat_id, user=user_text, source="telegram-voice")
    t0 = time.monotonic()

    await _send_typing(bot, chat_id)

    try:
        full_reply = await _stream_to_message(
            bot, chat_id, session_key, user_text, prefix=prefix,
        )
        elapsed = round((time.monotonic() - t0) * 1000)
        audit("res", chat_id=chat_id, assistant=full_reply[:500], ms=elapsed)

        parsed = parse_response(full_reply)
        spoken = parsed["spoken"]

        for att in parsed["attachments"]:
            try:
                escaped = att["content"].replace("\\", "\\\\").replace("`", "\\`")
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"```{att['language']}\n{escaped}\n```",
                    parse_mode="MarkdownV2",
                )
            except Exception:
                await bot.send_message(chat_id=chat_id, text=f"[{att['language']}]\n{att['content']}")

        if spoken:
            tts_t0 = time.monotonic()
            audio_data = await tts_synthesize(spoken)
            tts_ms = round((time.monotonic() - tts_t0) * 1000)
            if audio_data:
                audit("tts", chat_id=chat_id,
                      text_len=len(spoken), audio_bytes=len(audio_data), ms=tts_ms)
                await bot.send_voice(
                    chat_id=chat_id,
                    voice=io.BytesIO(audio_data),
                    caption="希露菲语音回复",
                )
    except Exception as e:
        log.error("Background voice reply failed: %s", e)
        try:
            await bot.send_message(chat_id=chat_id, text=f"抱歉，出了点问题：{e}")
        except Exception:
            pass


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_msg = update.message.text.strip()
    if not user_msg:
        return

    asyncio.create_task(_reply_text_task(
        ctx.bot, update.effective_chat.id, user_msg,
    ))


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    tg_file = await ctx.bot.get_file(voice.file_id)
    voice_bytes = await tg_file.download_as_bytearray()

    stt_t0 = time.monotonic()
    user_text = await stt_transcribe(bytes(voice_bytes), "audio.ogg")
    stt_ms = round((time.monotonic() - stt_t0) * 1000)

    if not user_text:
        await update.message.reply_text("没有识别到语音内容，请重试。")
        audit("stt", chat_id=update.effective_chat.id, text="", ms=stt_ms)
        return

    audit("stt", chat_id=update.effective_chat.id, text=user_text, ms=stt_ms)

    asyncio.create_task(_reply_voice_task(
        ctx.bot, update.effective_chat.id, user_text,
    ))


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    photo = update.message.photo[-1]
    tg_file = await ctx.bot.get_file(photo.file_id)
    photo_bytes = await tg_file.download_as_bytearray()

    b64 = base64.b64encode(bytes(photo_bytes)).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    caption = update.message.caption or ""
    audit("photo", chat_id=update.effective_chat.id, caption=caption,
          photo_size=len(photo_bytes))

    attachments = [{"mimeType": "image/jpeg", "content": b64}]
    asyncio.create_task(_reply_text_task_with_attachments(
        ctx.bot, update.effective_chat.id,
        caption or "请看看这张图片",
        attachments,
    ))


async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """处理文档上传（PDF/TXT/MD 等）——保存到临时目录，调用 docs_index 索引后对话。"""
    if not is_allowed(update):
        return

    doc = update.message.document
    if not doc:
        return

    filename = doc.file_name or "document"
    caption = update.message.caption or ""

    await _send_typing(ctx.bot, update.effective_chat.id)

    # 下载文件
    tg_file = await ctx.bot.get_file(doc.file_id)
    import tempfile
    with tempfile.NamedTemporaryFile(
        suffix=Path(filename).suffix or ".bin",
        prefix="tg_doc_",
        delete=False,
    ) as tmp:
        await tg_file.download_to_memory(tmp)
        tmp_path = tmp.name

    audit("doc_upload", chat_id=update.effective_chat.id,
          filename=filename, size=doc.file_size)

    # 通过 agent 处理（索引 + 回复）
    session_key = await _resolve_session(update.effective_chat.id)
    user_msg = caption or f"我上传了一个文档《{filename}》，请先帮我索引它，然后告诉我主要内容。"
    # 将临时路径注入到消息里供 docs_index 使用
    if not caption:
        user_msg = f"我上传了文档《{filename}》（已保存到 {tmp_path}），请用 docs_index 索引它，然后简要介绍内容。"

    asyncio.create_task(_reply_text_task(ctx.bot, update.effective_chat.id, user_msg))


async def handle_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    video = update.message.video or update.message.video_note
    if not video:
        return

    await _send_typing(ctx.bot, update.effective_chat.id)

    tg_file = await ctx.bot.get_file(video.file_id)
    video_bytes = await tg_file.download_as_bytearray()

    frames = extract_video_frames(bytes(video_bytes))
    if not frames:
        await update.message.reply_text("视频处理失败，请重试。")
        return

    caption = update.message.caption or ""
    audit("video", chat_id=update.effective_chat.id, caption=caption,
          video_size=len(video_bytes), frames=len(frames))

    msg = (f"{caption}\n（视频截取了{len(frames)}帧）" if caption
           else f"请看看这个视频（截取了{len(frames)}帧）")

    attachments = [{"mimeType": "image/jpeg", "content": f.split(",", 1)[1]} for f in frames]
    asyncio.create_task(_reply_text_task_with_attachments(
        ctx.bot, update.effective_chat.id, msg, attachments,
    ))


# ── Timer event handler ───────────────────────────────

async def _on_timer_fired(event: Event) -> None:
    global _bot_instance

    message = event.payload.get("message", "")
    if not message:
        log.warning("Timer fired with empty message, session=%s", event.session_key)
        return

    chat_id = session_to_chat_id(event.session_key)

    # Fengling web sessions（非 Telegram）：只走 Web Push，不走 Telegram
    if chat_id is None:
        log.info(
            "Timer fired for non-Telegram session '%s', delivering via Web Push only",
            event.session_key,
        )
        await _web_push_timer(message)
        audit("timer.fired", session_key=event.session_key, message=message[:200],
              timer_id=event.payload.get("timer_id", ""), channel="web_push")
        return

    if _bot_instance is None:
        log.error("Timer fired but bot instance not ready")
        return

    # Retry on transient network errors (e.g. ConnectTimeout)
    last_err = None
    for attempt in range(1, 4):
        try:
            await _bot_instance.send_message(chat_id=chat_id, text=message)
            audit("timer.fired", chat_id=chat_id, message=message[:200],
                  timer_id=event.payload.get("timer_id", ""))
            log.info("Timer delivered to chat_id=%s: %s", chat_id, message[:80])
            # 并发触发 Web Push（fire-and-forget，不影响 Telegram 成功状态）
            asyncio.create_task(_web_push_timer(message))
            return
        except Exception as e:
            last_err = e
            if attempt < 3:
                wait = 2 * attempt
                log.warning(
                    "Timer delivery attempt %s/3 failed (%s), retry in %ss",
                    attempt, type(e).__name__, wait,
                )
                await asyncio.sleep(wait)
    log.exception("Failed to deliver timer message to chat_id=%s after 3 attempts: %s", chat_id, last_err)


# ── Timer HTTP API ────────────────────────────────────

async def _web_push_timer(message: str) -> None:
    """Fire-and-forget Web Push for timer messages."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:{VOICE_CHAT_PORT}/api/push/send",
                json={"title": "风铃提醒", "body": message},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                log.info("Web Push timer sent=%s failed=%s", data.get("sent", 0), data.get("failed", 0))
    except Exception as e:
        log.warning("Web Push timer delivery failed: %s", e)

def _default_session_key() -> str:
    """Best-effort default: last active session, or tg-{ALLOWED_CHAT_ID}."""
    if _chat_ids:
        return next(iter(_chat_ids))
    if ALLOWED_CHAT_ID:
        return f"tg-{ALLOWED_CHAT_ID}"
    return ""


async def _api_create_timer(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid JSON"}, status=400)

    cron_expr = data.get("cron_expr", "").strip()
    delay = data.get("delay_seconds")
    session_key = data.get("session_key", "") or _default_session_key()
    message = data.get("message", "")
    label = data.get("label", "")
    intent = data.get("intent")  # optional semantic intent dict

    if not session_key:
        return web.json_response({"ok": False, "error": "session_key required (no default available)"}, status=400)
    if not message:
        return web.json_response({"ok": False, "error": "message required"}, status=400)

    if cron_expr:
        # Periodic cron timer
        try:
            from croniter import croniter
            if not croniter.is_valid(cron_expr):
                return web.json_response({"ok": False, "error": f"invalid cron expression: {cron_expr!r}"}, status=400)
        except ImportError:
            return web.json_response({"ok": False, "error": "croniter not installed"}, status=500)

        timer_id = await event_bus.schedule_cron(
            cron_expr=cron_expr,
            session_key=session_key,
            payload={"message": message},
            label=label,
            intent=intent,
        )
        audit("timer.created", session_key=session_key,
              cron_expr=cron_expr, message=message[:200], timer_id=timer_id)
        return web.json_response({"ok": True, "timer_id": timer_id, "cron_expr": cron_expr})
    else:
        # One-shot timer
        if not delay or not isinstance(delay, (int, float)) or delay <= 0:
            return web.json_response({"ok": False, "error": "delay_seconds must be > 0 (or provide cron_expr)"}, status=400)

        timer_id = await event_bus.schedule_timer(
            delay_seconds=float(delay),
            session_key=session_key,
            payload={"message": message},
            intent=intent,
        )
        audit("timer.created", session_key=session_key,
              delay_seconds=delay, message=message[:200], timer_id=timer_id)
        return web.json_response({"ok": True, "timer_id": timer_id, "delay_seconds": delay})


async def _api_list_timers(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "timers": event_bus.list_timers()})


async def _api_cancel_timer(request: web.Request) -> web.Response:
    timer_id = request.match_info.get("timer_id", "")
    if not timer_id:
        return web.json_response({"ok": False, "error": "timer_id required"}, status=400)
    cancelled = event_bus.cancel_timer(timer_id)
    if cancelled:
        audit("timer.cancelled", timer_id=timer_id)
    return web.json_response({"ok": cancelled})


def _create_api_app() -> web.Application:
    api = web.Application()
    api.router.add_post("/api/timer", _api_create_timer)
    api.router.add_get("/api/timers", _api_list_timers)
    api.router.add_delete("/api/timer/{timer_id}", _api_cancel_timer)
    api.router.add_get("/health", lambda _: web.json_response({"status": "ok"}))
    return api


# ── Main ─────────────────────────────────────────────

async def _async_main() -> None:
    global _bot_instance

    log.info(
        "Starting Telegram bot (model=%s, chat_id=%s, timer_api=:%s)",
        agent.model, ALLOWED_CHAT_ID, TIMER_API_PORT,
    )

    event_bus.subscribe("timer.fired", _on_timer_fired)
    await event_bus.restore_timers()

    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("help", cmd_help))
    tg_app.add_handler(CommandHandler("clear", cmd_clear))
    tg_app.add_handler(CommandHandler("timers", cmd_timers))
    tg_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    tg_app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    tg_app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    tg_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    api_app = _create_api_app()
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", TIMER_API_PORT)

    async with tg_app:
        _bot_instance = tg_app.bot
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        await site.start()
        log.info("Timer API listening on http://127.0.0.1:%s", TIMER_API_PORT)

        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            log.info("Shutting down...")
            await event_bus.shutdown()
            await tg_app.updater.stop()
            await tg_app.stop()
            await runner.cleanup()


def main():
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
