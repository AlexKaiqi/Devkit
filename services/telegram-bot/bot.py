"""
Telegram Bot for 希露菲 — text + voice + image + video conversations.
Routes all chat through OpenClaw Gateway for full Agent capabilities.
"""

import base64
import io
import json
import logging
import os
import subprocess
import tempfile
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
import re
import aiohttp

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from gateway_client import GatewayClient

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

# ── Gateway client (replaces direct LLM) ─────────────

GATEWAY_PORT = os.environ.get("OPENCLAW_GATEWAY_PORT", "18789")
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

gw = GatewayClient(
    gateway_url=f"ws://127.0.0.1:{GATEWAY_PORT}",
    token=GATEWAY_TOKEN,
    client_display_name="Telegram Bot",
    device_name="telegram-bot",
)

_session_keys: dict[int, str] = {}

# ── Audit ────────────────────────────────────────────

AUDIT_DIR = Path(os.environ.get(
    "AUDIT_DIR",
    Path(__file__).parent.parent.parent / "data" / "voice-audit",
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

CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def parse_response(text: str) -> dict:
    attachments = []
    for m in CODE_BLOCK_RE.finditer(text):
        attachments.append({
            "type": "code",
            "language": m.group(1) or "",
            "content": m.group(2).strip(),
        })
    spoken = CODE_BLOCK_RE.sub("", text).strip()
    spoken = re.sub(r"\n{3,}", "\n\n", spoken)
    return {"spoken": spoken, "attachments": attachments}


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


def extract_video_frames(video_bytes: bytes, max_frames: int = 4) -> list[str]:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        video_path = tmp.name
    out_dir = tempfile.mkdtemp()
    frames: list[str] = []
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(probe.stdout.strip() or "1")
        interval = max(duration / max_frames, 0.5)
        subprocess.run(
            ["ffmpeg", "-i", video_path,
             "-vf", f"fps=1/{interval:.2f},scale=512:-1",
             "-frames:v", str(max_frames), "-q:v", "5", "-y",
             f"{out_dir}/f%03d.jpg"],
            capture_output=True, timeout=60,
        )
        for fp in sorted(Path(out_dir).glob("f*.jpg")):
            b64 = base64.b64encode(fp.read_bytes()).decode()
            frames.append(f"data:image/jpeg;base64,{b64}")
            fp.unlink()
    except Exception as e:
        log.warning("frame extraction failed: %s", e)
    finally:
        if os.path.exists(video_path):
            os.unlink(video_path)
        try:
            os.rmdir(out_dir)
        except OSError:
            pass
    return frames


async def _resolve_session(chat_id: int) -> str:
    if chat_id in _session_keys:
        return _session_keys[chat_id]
    try:
        await gw.ensure_connected()
        friendly = f"telegram-{chat_id}"
        sk = await gw.resolve_session(friendly)
        _session_keys[chat_id] = sk
        return sk
    except Exception as e:
        log.error("Failed to resolve session: %s", e)
        sk = f"telegram-{chat_id}"
        _session_keys[chat_id] = sk
        return sk


async def chat_via_gateway(
    chat_id: int, user_msg: str, images: list[str] | None = None,
) -> str:
    """Send message through Gateway and collect full response."""
    session_key = await _resolve_session(chat_id)

    attachments = None
    if images:
        attachments = []
        for url in images:
            if url.startswith("data:"):
                header, b64data = url.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                attachments.append({"mimeType": mime, "content": b64data})

    t0 = time.monotonic()
    full_reply = ""
    try:
        async for evt in gw.chat_send(
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
        log.error("Gateway chat error: %s", e)

    elapsed = round((time.monotonic() - t0) * 1000)
    audit("chat", chat_id=chat_id, user=user_msg, assistant=full_reply[:500],
          images=len(images) if images else 0, ms=elapsed, source="gateway")
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
        "主人好，我是希露菲 🎀\n随时为您效劳，发文字、语音或图片都可以。"
    )


async def _send_code_block(update: Update, lang: str, code: str):
    try:
        escaped = code.replace("\\", "\\\\").replace("`", "\\`")
        await update.message.reply_text(
            f"```{lang}\n{escaped}\n```", parse_mode="MarkdownV2",
        )
    except Exception:
        await update.message.reply_text(f"[{lang}]\n{code}")


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_msg = update.message.text.strip()
    if not user_msg:
        return

    reply = await chat_via_gateway(update.effective_chat.id, user_msg)
    parsed = parse_response(reply)
    if parsed["spoken"]:
        await update.message.reply_text(parsed["spoken"])
    for att in parsed["attachments"]:
        await _send_code_block(update, att["language"], att["content"])


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    t0 = time.monotonic()

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

    reply = await chat_via_gateway(update.effective_chat.id, user_text)
    parsed = parse_response(reply)
    spoken = parsed["spoken"]

    display_text = f"🎤 {user_text}\n\n{spoken}" if spoken else f"🎤 {user_text}"
    await update.message.reply_text(display_text)
    for att in parsed["attachments"]:
        await _send_code_block(update, att["language"], att["content"])

    if spoken:
        tts_t0 = time.monotonic()
        audio_data = await tts_synthesize(spoken)
        tts_ms = round((time.monotonic() - tts_t0) * 1000)

        if audio_data:
            audit("tts", chat_id=update.effective_chat.id,
                  text_len=len(spoken), audio_bytes=len(audio_data), ms=tts_ms)
            await update.message.reply_voice(
                voice=io.BytesIO(audio_data),
                caption="希露菲语音回复",
            )

    total_ms = round((time.monotonic() - t0) * 1000)
    log.info("Voice round-trip: stt=%dms total=%dms", stt_ms, total_ms)


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

    reply = await chat_via_gateway(update.effective_chat.id, caption, images=[data_url])
    parsed = parse_response(reply)
    if parsed["spoken"]:
        await update.message.reply_text(parsed["spoken"])
    for att in parsed["attachments"]:
        await _send_code_block(update, att["language"], att["content"])


async def handle_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    video = update.message.video or update.message.video_note
    if not video:
        return

    await update.message.reply_text("正在分析视频...")

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
    reply = await chat_via_gateway(update.effective_chat.id, msg, images=frames)
    parsed = parse_response(reply)
    if parsed["spoken"]:
        await update.message.reply_text(parsed["spoken"])
    for att in parsed["attachments"]:
        await _send_code_block(update, att["language"], att["content"])


# ── Main ─────────────────────────────────────────────

def main():
    log.info("Starting Telegram bot (gateway=:%s, chat_id=%s)", GATEWAY_PORT, ALLOWED_CHAT_ID)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
