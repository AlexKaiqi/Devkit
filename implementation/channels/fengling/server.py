"""
Fengling channel service — push-to-talk voice interface.
Architecture: Browser ←→ FastAPI (STT + TTS) ←→ LocalAgent
"""

import base64
import asyncio
import gzip
import io
import logging
import os
import json
import re
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiohttp
import uvicorn

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))
from agent import AgentBackend, LocalAgent, get_traces, get_trace_by_id, get_trace_dates
from push_sender import send_all, save_subscription, remove_subscription, get_vapid_public_key
from watchlist_checker import WatchlistChecker
from calendar_checker import CalendarChecker
from tools import run_tool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_utils import parse_response, extract_video_frames, CODE_BLOCK_RE

# ── Logging ──────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voice-chat")

AUDIT_DIR = Path(os.environ.get(
    "AUDIT_DIR",
    Path(__file__).resolve().parents[2] / "data" / "voice-audit",
))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

CST = timezone(timedelta(hours=8))


def _audit_path() -> Path:
    return AUDIT_DIR / f"{datetime.now(CST).strftime('%Y-%m-%d')}.jsonl"


def audit(event: str, **kwargs):
    entry = {
        "ts": datetime.now(CST).isoformat(),
        "event": event,
        **kwargs,
    }
    log.info("[audit] %s %s", event, {k: v for k, v in kwargs.items() if k != "audio_size"})
    try:
        with open(_audit_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("audit write failed: %s", e)


# ── App setup ────────────────────────────────────────

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# SSE 广播队列：push_send 时往这里写，/api/notify-stream 消费
_notify_queues: list[asyncio.Queue] = []

STT_PROXY = os.environ.get("STT_PROXY_URL", "http://localhost:8787")

DOUBAO_APPID = os.environ.get("DOUBAO_APPID", "")
DOUBAO_TOKEN = os.environ.get("DOUBAO_TOKEN", "")
_TTS_PREFS_FILE = Path(__file__).resolve().parents[2] / "runtime" / "data" / "tts_prefs.json"


def _load_tts_voice() -> str:
    default = os.environ.get("TTS_VOICE", "BV001_streaming")
    try:
        if _TTS_PREFS_FILE.exists():
            prefs = json.loads(_TTS_PREFS_FILE.read_text(encoding="utf-8"))
            return prefs.get("voice", default)
    except Exception:
        pass
    return default


TTS_VOICE = _load_tts_voice()
TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.25"))

DOUBAO_TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"
DOUBAO_TTS_WS_URL = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"

# WS TTS binary protocol constants (火山引擎 streaming TTS)
_TTS_PROTOCOL_VER = 0b0001
_TTS_DEFAULT_HEADER_SIZE = 0b0001
# message types
_TTS_CLIENT_FULL_REQUEST = 0b0001
_TTS_CLIENT_AUDIO_REQUEST = 0b0010  # not used for TTS
_TTS_SERVER_FULL_RESPONSE = 0b1001
_TTS_SERVER_ACK = 0b1011
_TTS_SERVER_ERROR_RESPONSE = 0b1111
# message type specific flags
_TTS_NO_SEQUENCE = 0b0000
_TTS_POS_SEQUENCE = 0b0001
_TTS_NEG_WITH_SEQUENCE = 0b0011
# serialisation
_TTS_JSON = 0b0001
# compression
_TTS_NO_COMPRESS = 0b0000
_TTS_GZIP = 0b0001


def _tts_build_request(text: str, voice: str, speed: float, reqid: str) -> bytes:
    """Build the single full-client-request frame for TTS streaming."""
    payload_dict = {
        "app": {
            "appid": DOUBAO_APPID,
            "token": DOUBAO_TOKEN,
            "cluster": "volcano_tts",
        },
        "user": {"uid": "fengling"},
        "audio": {
            "voice_type": voice,
            "encoding": "mp3",
            "speed_ratio": speed,
            "sample_rate": 24000,
        },
        "request": {
            "reqid": reqid,
            "text": text,
            "text_type": "plain",
            "operation": "submit",
        },
    }
    payload_bytes = gzip.compress(json.dumps(payload_dict).encode())
    # header: version(4) | header_size(4) | msg_type(4) | msg_flags(4) | serial(4) | compress(4) | reserved(8)
    header = bytearray([
        (_TTS_PROTOCOL_VER << 4) | _TTS_DEFAULT_HEADER_SIZE,
        (_TTS_CLIENT_FULL_REQUEST << 4) | _TTS_NO_SEQUENCE,
        (_TTS_JSON << 4) | _TTS_GZIP,
        0x00,
    ])
    msg = header + len(payload_bytes).to_bytes(4, "big") + payload_bytes
    return bytes(msg)


async def _tts_ws_stream(text: str, voice: str, speed: float) -> AsyncIterator[bytes]:
    """Connect to Volcengine TTS WebSocket and yield raw MP3 chunks."""
    reqid = str(uuid.uuid4())
    ws_headers = {
        "Authorization": f"Bearer; {DOUBAO_TOKEN}",
    }
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            DOUBAO_TTS_WS_URL,
            headers=ws_headers,
        ) as ws:
            await ws.send_bytes(_tts_build_request(text, voice, speed, reqid))

            while True:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=15.0)
                except asyncio.TimeoutError:
                    log.warning("TTS WS timeout waiting for audio")
                    break

                if msg.type == aiohttp.WSMsgType.BINARY:
                    data = msg.data
                    if len(data) < 4:
                        continue
                    msg_type = (data[1] >> 4) & 0x0F
                    compress = data[2] & 0x0F
                    header_size = (data[0] & 0x0F) * 4
                    payload_raw = data[header_size:]

                    if msg_type == _TTS_SERVER_ERROR_RESPONSE:
                        # 4 bytes code + 4 bytes size + payload
                        code = int.from_bytes(payload_raw[:4], "big")
                        log.error("TTS WS error code=%d", code)
                        break

                    if msg_type in (_TTS_SERVER_FULL_RESPONSE, _TTS_SERVER_ACK):
                        # sequence(4) + payload_size(4) + audio_bytes  OR  just sequence
                        offset = 0
                        msg_flags = data[1] & 0x0F
                        if msg_flags in (_TTS_POS_SEQUENCE, _TTS_NEG_WITH_SEQUENCE):
                            seq = int.from_bytes(payload_raw[:4], "big", signed=True)
                            offset = 4
                        if len(payload_raw) > offset + 4:
                            payload_size = int.from_bytes(
                                payload_raw[offset:offset + 4], "big"
                            )
                            audio_data = payload_raw[offset + 4:offset + 4 + payload_size]
                            if compress == _TTS_GZIP and audio_data:
                                try:
                                    audio_data = gzip.decompress(audio_data)
                                except Exception:
                                    pass  # may already be raw mp3
                            if audio_data:
                                yield audio_data

                        # negative seq = last frame
                        if msg_flags == _TTS_NEG_WITH_SEQUENCE:
                            break

                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break

VOICES = [
    {"id": "BV001_streaming", "name": "通用女声(流式)", "gender": "女", "tag": "流式"},
    {"id": "zh_female_tianmeixiaoyuan_moon_bigtts", "name": "甜美小源", "gender": "女", "tag": "甜美"},
    {"id": "zh_female_cancan_mars_bigtts", "name": "灿灿", "gender": "女", "tag": "通用"},
    {"id": "zh_female_linjianvhai_moon_bigtts", "name": "邻家女孩", "gender": "女", "tag": "自然"},
    {"id": "zh_female_qingxinnvsheng_mars_bigtts", "name": "清新女声", "gender": "女", "tag": "清新"},
    {"id": "zh_female_zhixingnvsheng_mars_bigtts", "name": "知性女声", "gender": "女", "tag": "知性"},
    {"id": "zh_female_shuangkuaisisi_moon_bigtts", "name": "爽快思思", "gender": "女", "tag": "爽朗"},
    {"id": "zh_female_qingchezizi_moon_bigtts", "name": "清澈梓梓", "gender": "女", "tag": "清澈"},
    {"id": "zh_female_kailangjiejie_moon_bigtts", "name": "开朗姐姐", "gender": "女", "tag": "开朗"},
    {"id": "zh_female_tianmeiyueyue_moon_bigtts", "name": "甜美悦悦", "gender": "女", "tag": "甜美"},
    {"id": "zh_female_xinlingjitang_moon_bigtts", "name": "心灵鸡汤", "gender": "女", "tag": "温暖"},
    {"id": "zh_female_wenrouxiaoya_moon_bigtts", "name": "温柔小雅", "gender": "女", "tag": "温柔"},
    {"id": "zh_female_sajiaonvyou_moon_bigtts", "name": "柔美女友", "gender": "女", "tag": "柔美"},
    {"id": "zh_female_gaolengyujie_moon_bigtts", "name": "高冷御姐", "gender": "女", "tag": "御姐"},
    {"id": "zh_female_meilinvyou_moon_bigtts", "name": "魅力女友", "gender": "女", "tag": "魅力"},
    {"id": "ICL_zh_female_keainvsheng_tob", "name": "可爱女生", "gender": "女", "tag": "可爱"},
    {"id": "ICL_zh_female_tiexinnvyou_tob", "name": "贴心女友", "gender": "女", "tag": "贴心"},
    {"id": "ICL_zh_female_huoponvhai_tob", "name": "活泼女孩", "gender": "女", "tag": "活泼"},
    {"id": "ICL_zh_female_jiaoruoluoli_tob", "name": "娇弱萝莉", "gender": "女", "tag": "萝莉"},
    {"id": "ICL_zh_female_nuanxinxuejie_tob", "name": "暖心学姐", "gender": "女", "tag": "温暖"},
    {"id": "zh_female_roumeinvyou_emo_v2_mars_bigtts", "name": "柔美女友(多情感)", "gender": "女", "tag": "情感"},
    {"id": "zh_female_shuangkuaisisi_emo_v2_mars_bigtts", "name": "爽快思思(多情感)", "gender": "女", "tag": "情感"},
    {"id": "zh_male_wennuanahu_moon_bigtts", "name": "温暖阿虎", "gender": "男", "tag": "温暖"},
    {"id": "zh_male_shaonianzixin_moon_bigtts", "name": "少年梓辛", "gender": "男", "tag": "少年"},
    {"id": "zh_male_yangguangqingnian_moon_bigtts", "name": "阳光青年", "gender": "男", "tag": "阳光"},
    {"id": "zh_male_linjiananhai_moon_bigtts", "name": "邻家男孩", "gender": "男", "tag": "自然"},
]

# ── Agent ─────────────────────────────────────────────

agent = LocalAgent()

_session_keys: dict[str, str] = {}


@app.on_event("startup")
async def _startup():
    """Try to init task graph on startup (non-blocking if Neo4j is not available)."""
    await agent.init_task_graph()
    await agent.init_methodology()

    # Start watchlist background checker
    _watchlist_data = Path(__file__).resolve().parents[2] / "runtime" / "data" / "watchlist.json"
    checker = WatchlistChecker(data_path=_watchlist_data, run_tool_fn=run_tool)
    await checker.start()

    # Start calendar reminders background checker
    _calendar_data = Path(__file__).resolve().parents[2] / "runtime" / "data" / "calendar_reminders.json"
    cal_checker = CalendarChecker(data_path=_calendar_data, run_tool_fn=run_tool)
    await cal_checker.start()


_http: aiohttp.ClientSession | None = None


async def get_http() -> aiohttp.ClientSession:
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession()
    return _http


@app.on_event("shutdown")
async def _shutdown():
    if _http and not _http.closed:
        await _http.close()
    pass


# ── Routes ───────────────────────────────────────────

@app.get("/")
async def index():
    return HTMLResponse(
        (STATIC_DIR / "index.html").read_text(),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/manifest.json")
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


# ── Push API ─────────────────────────────────────────────────

@app.get("/api/push/vapid-public-key")
async def push_vapid_key():
    key = get_vapid_public_key()
    if not key:
        return JSONResponse({"error": "VAPID keys not generated"}, status_code=503)
    return {"publicKey": key}


@app.post("/api/push/subscribe")
async def push_subscribe(request: Request):
    sub = await request.json()
    save_subscription(sub)
    return {"ok": True}


@app.delete("/api/push/subscribe")
async def push_unsubscribe(request: Request):
    body = await request.json()
    endpoint = body.get("endpoint", "")
    if endpoint:
        remove_subscription(endpoint)
    return {"ok": True}


@app.post("/api/push/send")
async def push_send(request: Request):
    body = await request.json()
    title = body.get("title", "风铃")
    msg_body = body.get("body", "")
    result = await send_all(title, msg_body)
    # 同时广播到所有已连接的 SSE 客户端（页面内消息流）
    dead = []
    for q in _notify_queues:
        try:
            q.put_nowait(msg_body)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _notify_queues.remove(q)
    return result


@app.get("/api/notify-stream")
async def notify_stream(request: Request):
    """SSE 端点：服务器主动推送消息到页面对话流。"""
    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _notify_queues.append(q)

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps({'body': msg}, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if q in _notify_queues:
                _notify_queues.remove(q)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    t0 = time.monotonic()
    audio_bytes = await audio.read()
    form = aiohttp.FormData()
    form.add_field(
        "file", audio_bytes,
        filename=audio.filename or "audio.webm",
        content_type=audio.content_type or "audio/webm",
    )
    form.add_field("model", "whisper-1")
    form.add_field("language", "zh")

    http = await get_http()
    async with http.post(
        f"{STT_PROXY}/v1/audio/transcriptions", data=form
    ) as resp:
        result = await resp.json()

    elapsed = round((time.monotonic() - t0) * 1000)
    audit("stt", text=result.get("text", ""), audio_size=len(audio_bytes), ms=elapsed)
    return result


@app.post("/api/extract-frames")
async def api_extract_frames(video: UploadFile = File(...)):
    data = await video.read()
    frames = extract_video_frames(data)
    audit("extract_frames", frame_count=len(frames), video_size=len(data))
    return {"frames": frames}


async def _resolve_session(session_id: str) -> str:
    if session_id in _session_keys:
        return _session_keys[session_id]
    sk = f"fengling-{session_id[:8]}"
    _session_keys[session_id] = sk
    return sk


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    user_msg = body.get("message", "")
    session_id = body.get("session_id", "default")
    images = body.get("images", [])

    session_key = await _resolve_session(session_id)
    t0 = time.monotonic()

    attachments = None
    if images:
        attachments = []
        for url in images:
            if url.startswith("data:"):
                header, b64data = url.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                attachments.append({"mimeType": mime, "content": b64data})

    async def generate():
        full_response = ""
        first_token_ms = None
        try:
            async for evt in agent.chat_send(session_key, user_msg or "请看看这些内容", attachments=attachments):
                if evt["type"] == "text":
                    if first_token_ms is None:
                        first_token_ms = round((time.monotonic() - t0) * 1000)
                    full_response += evt["content"]
                    yield f"data: {json.dumps({'type': 'text', 'content': evt['content']})}\n\n"

                elif evt["type"] == "tool":
                    yield f"data: {json.dumps({'type': 'tool', 'name': evt.get('name', ''), 'status': evt.get('status', '')})}\n\n"

                elif evt["type"] == "done":
                    full_response = evt.get("full_text", full_response)
                    total_ms = round((time.monotonic() - t0) * 1000)
                    audit(
                        "chat", session=session_id, user=user_msg,
                        assistant=full_response[:500],
                        images=len(images) if images else 0,
                        first_token_ms=first_token_ms, total_ms=total_ms,
                        source="fengling",
                    )
                    parsed = parse_response(full_response)
                    yield f"data: {json.dumps({'type': 'done', 'full_text': full_response, 'spoken': parsed['spoken'], 'attachments': parsed['attachments']})}\n\n"

                elif evt["type"] == "error":
                    audit("chat_error", session=session_id, user=user_msg, error=evt["content"])
                    yield f"data: {json.dumps({'type': 'error', 'content': evt['content']})}\n\n"

        except Exception as e:
            audit("chat_error", session=session_id, user=user_msg, error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/tts")
async def text_to_speech(request: Request):
    t0 = time.monotonic()
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", TTS_VOICE)

    if not text.strip():
        return JSONResponse({"error": "empty text"}, status_code=400)

    payload = {
        "app": {
            "appid": DOUBAO_APPID,
            "token": "access_token",
            "cluster": "volcano_tts",
        },
        "user": {"uid": "voice-chat"},
        "audio": {
            "voice_type": voice,
            "encoding": "mp3",
            "speed_ratio": TTS_SPEED,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "operation": "query",
        },
    }

    http = await get_http()
    async with http.post(
        DOUBAO_TTS_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer; {DOUBAO_TOKEN}",
        },
        json=payload,
    ) as resp:
        result = await resp.json()

        elapsed = round((time.monotonic() - t0) * 1000)

        if result.get("code") != 3000:
            audit("tts_error", voice=voice, text=text[:100], error=result.get("message", ""), ms=elapsed)
            return JSONResponse(
                {"error": result.get("message", "TTS failed")},
                status_code=502,
            )

        audio_data = base64.b64decode(result["data"])
        audit("tts", voice=voice, text_len=len(text), audio_bytes=len(audio_data), ms=elapsed)
        return StreamingResponse(
            io.BytesIO(audio_data), media_type="audio/mpeg"
        )


@app.get("/api/voices")
async def list_voices():
    return {"voices": VOICES, "current": TTS_VOICE}


@app.put("/api/voices/preference")
async def set_voice_preference(request: Request):
    global TTS_VOICE
    body = await request.json()
    voice_id = body.get("voice", "").strip()
    valid_ids = {v["id"] for v in VOICES}
    if not voice_id or voice_id not in valid_ids:
        return JSONResponse({"error": "invalid voice"}, status_code=400)
    TTS_VOICE = voice_id
    try:
        _TTS_PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TTS_PREFS_FILE.write_text(json.dumps({"voice": voice_id}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("tts_prefs write failed: %s", e)
    return {"voice": TTS_VOICE}


@app.post("/api/tts/stream")
async def tts_stream(request: Request):
    """Streaming TTS via Volcengine WS binary protocol — MP3 chunks arrive progressively."""
    t0 = time.monotonic()
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", TTS_VOICE)

    if not text.strip():
        return JSONResponse({"error": "empty text"}, status_code=400)

    async def generate():
        total = 0
        try:
            async for chunk in _tts_ws_stream(text, voice, TTS_SPEED):
                total += len(chunk)
                yield chunk
        except Exception as e:
            log.error("tts_stream error: %s", e)
        elapsed = round((time.monotonic() - t0) * 1000)
        audit("tts_stream", voice=voice, text_len=len(text), audio_bytes=total, ms=elapsed)

    return StreamingResponse(generate(), media_type="audio/mpeg")

@app.get("/api/audit")
async def get_audit(date: str = ""):
    if not date:
        date = datetime.now(CST).strftime("%Y-%m-%d")
    path = AUDIT_DIR / f"{date}.jsonl"
    if not path.exists():
        return {"date": date, "count": 0, "entries": []}
    entries = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return {"date": date, "count": len(entries), "entries": entries}


@app.get("/api/audit/dates")
async def get_audit_dates():
    """返回有审计记录的日期列表，最新在前。"""
    if not AUDIT_DIR.exists():
        return {"dates": []}
    dates = sorted(
        [p.stem for p in AUDIT_DIR.glob("*.jsonl")],
        reverse=True,
    )
    return {"dates": dates}


# ── Task Graph API ──────────────────────────────────

@app.get("/api/tasks")
async def list_tasks(session_id: str = ""):
    """List root tasks for a session (or all sessions)."""
    if not agent._task_orchestrator:
        return JSONResponse({"error": "Task graph not available"}, status_code=503)
    if session_id:
        session_key = await _resolve_session(session_id)
    else:
        session_key = ""
    if session_key:
        root_tasks = await agent._task_graph_store.get_session_root_tasks(session_key)
        return {"session_key": session_key, "tasks": [t.model_dump() for t in root_tasks]}
    # List all root tasks across sessions
    async with agent._task_graph_store._driver.session() as session:
        result = await session.run(
            "MATCH (t:Task) WHERE NOT (t)-[:SUBTASK_OF]->() RETURN t ORDER BY t.created_at DESC LIMIT 100"
        )
        records = await result.data()
    from task_graph.models import TaskNode
    tasks = [TaskNode.from_neo4j_record(dict(r["t"])) for r in records]
    return {"tasks": [t.model_dump() for t in tasks]}


@app.get("/api/tasks/{task_id}")
async def get_task_detail(task_id: str):
    """Get a single task's details."""
    if not agent._task_orchestrator:
        return JSONResponse({"error": "Task graph not available"}, status_code=503)
    result = await agent._task_orchestrator.get_task_status(task_id=task_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return result


@app.get("/api/tasks/{task_id}/tree")
async def get_task_tree(task_id: str):
    """Get the full subtask tree under a task."""
    if not agent._task_graph_store:
        return JSONResponse({"error": "Task graph not available"}, status_code=503)
    tree = await agent._task_graph_store.get_subtree(task_id)
    if not tree:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return tree


@app.put("/api/tasks/{task_id}")
async def update_task_api(task_id: str, request: Request):
    """Update a task (pause/cancel/priority)."""
    if not agent._task_orchestrator:
        return JSONResponse({"error": "Task graph not available"}, status_code=503)
    body = await request.json()
    task = await agent._task_orchestrator.update_task(
        task_id=task_id,
        state=body.get("state"),
        priority=body.get("priority"),
        next_action=body.get("next_action"),
    )
    return {"task_id": task.task_id, "state": task.state.value}


@app.post("/api/tasks/{task_id}/subtasks")
async def add_subtask_api(task_id: str, request: Request):
    """Manually add a subtask."""
    if not agent._task_orchestrator:
        return JSONResponse({"error": "Task graph not available"}, status_code=503)
    body = await request.json()
    parent = await agent._task_graph_store.get_task(task_id)
    if not parent:
        return JSONResponse({"error": "Parent task not found"}, status_code=404)
    child = await agent._task_orchestrator.create_task(
        session_key=parent.session_key,
        title=body.get("title", "New subtask"),
        intent=body.get("intent", ""),
        parent_task_id=task_id,
    )
    return {"task_id": child.task_id, "title": child.title, "state": child.state.value}


@app.get("/api/tasks/events")
async def task_events_sse(request: Request, session_id: str = ""):
    """SSE endpoint for real-time task state changes."""
    import asyncio

    if not agent._task_orchestrator or not hasattr(agent, '_task_graph_store'):
        return JSONResponse({"error": "Task graph not available"}, status_code=503)

    async def event_generator():
        # Poll-based SSE: check for changes every 2 seconds
        last_states: dict[str, str] = {}
        while True:
            if await request.is_disconnected():
                break
            try:
                # Get all non-terminal tasks
                async with agent._task_graph_store._driver.session() as neo_session:
                    result = await neo_session.run(
                        "MATCH (t:Task) RETURN t.task_id AS id, t.state AS state, t.title AS title, t.updated_at AS updated"
                    )
                    records = await result.data()

                current_states = {r["id"]: r["state"] for r in records}

                # Find changes
                for tid, state in current_states.items():
                    if tid not in last_states or last_states[tid] != state:
                        rec = next((r for r in records if r["id"] == tid), None)
                        if rec:
                            evt_data = json.dumps({
                                "task_id": tid,
                                "state": state,
                                "title": rec.get("title", ""),
                                "updated_at": rec.get("updated", 0),
                            })
                            yield f"data: {evt_data}\n\n"

                last_states = current_states
            except Exception:
                pass

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Ops Page ─────────────────────────────────────────

@app.get("/ops")
async def ops_page():
    ops_html = STATIC_DIR / "ops.html"
    return HTMLResponse(ops_html.read_text(), headers={"Cache-Control": "no-store"})


@app.get("/api/ops/status")
async def ops_status():
    """综合运维状态快照。"""
    import platform
    import psutil

    # ── 服务健康 ──
    services = {}
    async def _ping(name: str, url: str):
        try:
            http = await get_http()
            async with http.get(url, timeout=aiohttp.ClientTimeout(total=2)) as r:
                services[name] = "ok" if r.status < 500 else "error"
        except Exception:
            services[name] = "down"

    await asyncio.gather(
        _ping("stt_proxy", f"http://localhost:{os.environ.get('STT_PROXY_PORT', '8787')}/health"),
        _ping("timer_api", f"http://localhost:{os.environ.get('TIMER_API_PORT', '8789')}/health"),
        _ping("openrouter-proxy", f"http://localhost:{os.environ.get('CLAUDE_CODE_PROXY_PORT', '9999')}/v1/models"),
        _ping("searxng", f"http://localhost:{os.environ.get('SEARXNG_PORT', '8080')}/healthz"),
        _ping("neo4j", f"http://localhost:{os.environ.get('NEO4J_HTTP_PORT', '7474')}"),
        return_exceptions=True,
    )
    services["fengling"] = "ok"  # 自身肯定在线

    # ── 系统资源 ──
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        system = {
            "cpu_pct": cpu,
            "mem_used_gb": round(mem.used / 1024**3, 1),
            "mem_total_gb": round(mem.total / 1024**3, 1),
            "mem_pct": mem.percent,
            "disk_used_gb": round(disk.used / 1024**3, 1),
            "disk_total_gb": round(disk.total / 1024**3, 1),
            "disk_pct": disk.percent,
        }
    except Exception:
        system = {}

    # ── Timers ──
    try:
        import aiohttp as _ah
        http = await get_http()
        async with http.get(
            f"http://localhost:{os.environ.get('TIMER_API_PORT', '8789')}/api/timers",
            timeout=aiohttp.ClientTimeout(total=2),
        ) as r:
            timer_data = await r.json()
            timers = timer_data.get("timers", [])
    except Exception:
        timers = []

    # ── Watchlist ──
    watchlist_path = Path(__file__).resolve().parents[2] / "runtime" / "data" / "watchlist.json"
    try:
        watchlist = json.loads(watchlist_path.read_text()) if watchlist_path.exists() else []
    except Exception:
        watchlist = []

    # ── Calendar Reminders ──
    calendar_reminders_path = Path(__file__).resolve().parents[2] / "runtime" / "data" / "calendar_reminders.json"
    try:
        calendar_reminders = json.loads(calendar_reminders_path.read_text()) if calendar_reminders_path.exists() else []
    except Exception:
        calendar_reminders = []

    # 预计算每条日历提醒的下次触发公历日期，供前端展示
    from calendar_checker import next_solar_date_for_holiday, next_solar_date_for_lunar, _next_solar_date_for_solar
    from datetime import date as _date
    _today = _date.today()
    for _entry in calendar_reminders:
        try:
            _adv = int(_entry.get("advance_days", 0))
            _t = _entry.get("type", "")
            _target = None
            if _t == "holiday":
                _target = next_solar_date_for_holiday(_entry.get("name", ""), _today)
            elif _t == "lunar_date":
                _target = next_solar_date_for_lunar(
                    int(_entry.get("lunar_month", 0)), int(_entry.get("lunar_day", 0)), _today
                )
            elif _t == "solar_date":
                _target = _next_solar_date_for_solar(
                    int(_entry.get("solar_month", 0)), int(_entry.get("solar_day", 0)), _today
                )
            if _target:
                from datetime import timedelta
                _remind = _target - timedelta(days=_adv)
                _entry["next_trigger_date"] = _remind.isoformat()
                _entry["next_event_date"] = _target.isoformat()
        except Exception:
            pass

    # ── Background processes ──
    try:
        from tools.skills.process.process import _REGISTRY
        processes = [e.to_dict() for e in _REGISTRY.values()]
    except Exception:
        processes = []

    # ── Sessions ──
    sessions_dir = Path(__file__).resolve().parents[2] / "runtime" / "data" / "sessions"
    sessions = []
    if sessions_dir.exists():
        for f in sorted(sessions_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
            try:
                msgs = json.loads(f.read_text())
                sessions.append({
                    "key": f.stem,
                    "messages": len(msgs),
                    "mtime": f.stat().st_mtime,
                })
            except Exception:
                pass

    # ── Recent audit ──
    today = datetime.now(CST).strftime("%Y-%m-%d")
    audit_entries = []
    audit_path = AUDIT_DIR / f"{today}.jsonl"
    if audit_path.exists():
        try:
            lines = audit_path.read_text().strip().splitlines()
            for line in reversed(lines[-50:]):
                if line:
                    audit_entries.append(json.loads(line))
        except Exception:
            pass
    audit_entries = audit_entries[:30]

    return {
        "ts": datetime.now(CST).isoformat(),
        "services": services,
        "system": system,
        "timers": timers,
        "watchlist": watchlist,
        "calendar_reminders": calendar_reminders,
        "processes": processes,
        "sessions": sessions,
        "audit": audit_entries,
        "agent_model": agent.model,
    }


@app.get("/api/ops/memory")
async def ops_memory():
    """解析 MEMORY.md，按 ## 节返回结构化记忆条目。"""
    workspace = Path(os.environ.get("WORKSPACE_DIR", "implementation/assets/persona"))
    if not workspace.is_absolute():
        workspace = Path(__file__).resolve().parents[3] / workspace
    memory_path = workspace / "MEMORY.md"

    if not memory_path.exists():
        return {"sections": [], "raw": ""}

    raw = memory_path.read_text(encoding="utf-8")
    sections = []
    current_title = "概述"
    current_items: list[str] = []

    for line in raw.splitlines():
        if line.startswith("## "):
            if current_items:
                sections.append({"title": current_title, "items": current_items})
            current_title = line[3:].strip()
            current_items = []
        elif line.strip().startswith("- "):
            current_items.append(line.strip()[2:].strip())
        elif line.strip() and not line.startswith("#") and not line.startswith(">"):
            # 非列表的普通文本行也收入
            current_items.append(line.strip())

    if current_items:
        sections.append({"title": current_title, "items": current_items})

    # 今日日志（最新 3 天）
    memory_dir = workspace / "memory"
    daily_logs = []
    if memory_dir.exists():
        for f in sorted(memory_dir.glob("*.md"), reverse=True)[:3]:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                daily_logs.append({"date": f.stem, "content": content})

    return {"sections": sections, "daily_logs": daily_logs}


@app.get("/api/ops/product")
async def ops_product():
    """返回产品功能与设计概览：目标、Skills、能力表、最近进展。"""
    root = Path(__file__).resolve().parents[3]

    def _read(rel: str) -> str:
        p = root / rel
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _parse_h2_sections(text: str) -> list[dict]:
        """把 ## 标题下的内容解析为 {title, body} 列表。"""
        sections, title, lines = [], "", []
        for line in text.splitlines():
            if line.startswith("## "):
                if title:
                    sections.append({"title": title, "body": "\n".join(lines).strip()})
                title, lines = line[3:].strip(), []
            elif title:
                lines.append(line)
        if title:
            sections.append({"title": title, "body": "\n".join(lines).strip()})
        return sections

    # ── 产品目标（摘取关键节）──
    goals_text = _read("requirements/product/goals.md")
    goals_sections = _parse_h2_sections(goals_text)

    # ── Skills 列表 ──
    skills = []
    skills_dir = root / "implementation/runtime/tools/skills"
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        raw = skill_md.read_text(encoding="utf-8")
        # Parse YAML frontmatter
        import re as _re
        fm = {}
        fm_match = _re.match(r"^---\n(.*?)\n---", raw, _re.DOTALL)
        if fm_match:
            for kv in fm_match.group(1).splitlines():
                if ":" in kv:
                    k, _, v = kv.partition(":")
                    fm[k.strip()] = v.strip()
        # Parse description line (first non-empty line after frontmatter)
        desc_lines = [l for l in raw.split("---", 2)[-1].strip().splitlines()
                      if l.strip() and not l.startswith("#")]
        desc = desc_lines[0].strip() if desc_lines else ""
        # Parse keywords from frontmatter
        kw_raw = fm.get("keywords", "[]")
        keywords = [k.strip().strip("'\"") for k in kw_raw.strip("[]").split(",") if k.strip()]
        skills.append({
            "name": fm.get("name", skill_dir.name),
            "always": fm.get("always", "false").lower() == "true",
            "keywords": keywords[:8],  # top 8
            "description": desc,
        })

    # ── 能力总览表 ──
    capabilities_text = _read("requirements/capabilities/overview.md")

    # ── 最近进展（STATUS.md 前 60 行）──
    status_text = _read("implementation/STATUS.md")
    status_lines = status_text.splitlines()
    # Find 最近完成 section
    recent = []
    in_recent = False
    for line in status_lines:
        if line.startswith("## 最近完成"):
            in_recent = True
            continue
        if in_recent:
            if line.startswith("## ") and "最近" not in line:
                break
            if line.strip():
                recent.append(line)
            if len(recent) > 30:
                break

    # ── 当前迭代重点 ──
    iteration_focus = []
    in_iter = False
    for line in goals_sections:
        if "迭代" in line["title"] or "重点" in line["title"]:
            iteration_focus = [l for l in line["body"].splitlines()
                               if l.strip() and not l.startswith("#")]
            break

    return {
        "goals_sections": goals_sections,
        "skills": skills,
        "capabilities_text": capabilities_text,
        "recent_progress": recent,
        "iteration_focus": iteration_focus,
        "agent_model": agent.model,
    }



    """清空指定会话历史。"""
    if session_key in agent._sessions:
        agent._sessions[session_key] = []
    agent._save_session(session_key)
    return {"ok": True}


@app.delete("/api/ops/timers/{timer_id}")
async def ops_cancel_timer(timer_id: str):
    """通过 Timer API 取消提醒。"""
    try:
        http = await get_http()
        async with http.delete(
            f"http://localhost:{os.environ.get('TIMER_API_PORT', '8789')}/api/timer/{timer_id}",
            timeout=aiohttp.ClientTimeout(total=3),
        ) as r:
            return await r.json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.delete("/api/ops/watchlist/{watch_id}")
async def ops_remove_watch(watch_id: str):
    """删除 watchlist 订阅。"""
    watchlist_path = Path(__file__).resolve().parents[2] / "runtime" / "data" / "watchlist.json"
    try:
        entries = json.loads(watchlist_path.read_text()) if watchlist_path.exists() else []
        before = len(entries)
        entries = [e for e in entries if e.get("watch_id") != watch_id]
        watchlist_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
        return {"ok": True, "removed": before - len(entries)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.delete("/api/ops/calendar-reminders/{reminder_id}")
async def ops_remove_calendar_reminder(reminder_id: str):
    """删除日历提醒（节日/农历日期）。"""
    cal_path = Path(__file__).resolve().parents[2] / "runtime" / "data" / "calendar_reminders.json"
    try:
        entries = json.loads(cal_path.read_text()) if cal_path.exists() else []
        before = len(entries)
        entries = [e for e in entries if e.get("id") != reminder_id]
        cal_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
        return {"ok": True, "removed": before - len(entries)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.delete("/api/ops/processes/{pid}")
async def ops_kill_process(pid: int):
    """终止后台进程。"""
    try:
        from tools.skills.process.process import _REGISTRY
        entry = _REGISTRY.get(pid)
        if not entry:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        entry._proc.kill()
        entry.state = "killed"
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/ops/traces")
async def ops_traces(limit: int = 50, date: str | None = None):
    """返回执行轨迹列表。date=YYYY-MM-DD 时从归档读取，否则从内存读取当日。"""
    traces = get_traces(limit, date=date)
    summaries = []
    for t in traces:
        summaries.append({
            "id": t["id"],
            "ts": t["ts"],
            "session_key": t["session_key"],
            "user": t["user"],
            "status": t["status"],
            "total_ms": t.get("total_ms", 0),
            "steps_count": len(t.get("steps", [])),
            "error": t.get("error", ""),
            "reply": t.get("reply", "")[:100],
        })
    return {"traces": summaries}


@app.get("/api/ops/traces/dates")
async def ops_trace_dates():
    """返回有归档记录的日期列表，最新在前。"""
    return {"dates": get_trace_dates()}


@app.get("/api/ops/traces/{trace_id}")
async def ops_trace_detail(trace_id: str, date: str | None = None):
    """返回单条 trace 的完整执行详情。"""
    trace = get_trace_by_id(trace_id, date=date)
    if not trace:
        return JSONResponse({"error": "not found"}, status_code=404)
    return trace


if __name__ == "__main__":
    port = int(os.environ.get("VOICE_CHAT_PORT", "3001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
