"""
Voice Chat Service — push-to-talk voice interface for 希露菲.
Architecture: Browser ←→ FastAPI (STT proxy + LLM + TTS) ←→ Doubao/LLM
"""

import base64
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

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
import aiohttp
import uvicorn

# ── Logging ──────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voice-chat")

AUDIT_DIR = Path(os.environ.get(
    "AUDIT_DIR",
    Path(__file__).parent.parent.parent / "data" / "voice-audit",
))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

CST = timezone(timedelta(hours=8))


def _audit_path() -> Path:
    return AUDIT_DIR / f"{datetime.now(CST).strftime('%Y-%m-%d')}.jsonl"


def audit(event: str, **kwargs):
    """Append one JSON line per interaction to daily audit file."""
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

STT_PROXY = os.environ.get("STT_PROXY_URL", "http://localhost:8787")

DOUBAO_APPID = os.environ.get("DOUBAO_APPID", "")
DOUBAO_TOKEN = os.environ.get("DOUBAO_TOKEN", "")
TTS_VOICE = os.environ.get("TTS_VOICE", "zh_female_tianmeixiaoyuan_moon_bigtts")
TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.25"))

DOUBAO_TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"

VOICES = [
    # 大模型通用场景
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
    # 大模型角色扮演
    {"id": "zh_female_sajiaonvyou_moon_bigtts", "name": "柔美女友", "gender": "女", "tag": "柔美"},
    {"id": "zh_female_gaolengyujie_moon_bigtts", "name": "高冷御姐", "gender": "女", "tag": "御姐"},
    {"id": "zh_female_meilinvyou_moon_bigtts", "name": "魅力女友", "gender": "女", "tag": "魅力"},
    {"id": "ICL_zh_female_keainvsheng_tob", "name": "可爱女生", "gender": "女", "tag": "可爱"},
    {"id": "ICL_zh_female_tiexinnvyou_tob", "name": "贴心女友", "gender": "女", "tag": "贴心"},
    {"id": "ICL_zh_female_huoponvhai_tob", "name": "活泼女孩", "gender": "女", "tag": "活泼"},
    {"id": "ICL_zh_female_jiaoruoluoli_tob", "name": "娇弱萝莉", "gender": "女", "tag": "萝莉"},
    {"id": "ICL_zh_female_nuanxinxuejie_tob", "name": "暖心学姐", "gender": "女", "tag": "温暖"},
    # 大模型多情感
    {"id": "zh_female_roumeinvyou_emo_v2_mars_bigtts", "name": "柔美女友(多情感)", "gender": "女", "tag": "情感"},
    {"id": "zh_female_shuangkuaisisi_emo_v2_mars_bigtts", "name": "爽快思思(多情感)", "gender": "女", "tag": "情感"},
    # 大模型男声
    {"id": "zh_male_wennuanahu_moon_bigtts", "name": "温暖阿虎", "gender": "男", "tag": "温暖"},
    {"id": "zh_male_shaonianzixin_moon_bigtts", "name": "少年梓辛", "gender": "男", "tag": "少年"},
    {"id": "zh_male_yangguangqingnian_moon_bigtts", "name": "阳光青年", "gender": "男", "tag": "阳光"},
    {"id": "zh_male_linjiananhai_moon_bigtts", "name": "邻家男孩", "gender": "男", "tag": "自然"},
]

llm = AsyncOpenAI(
    api_key=os.environ.get("LLM_API_KEY", ""),
    base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
)
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
VISION_MODEL = os.environ.get("VISION_MODEL", LLM_MODEL)

SYSTEM_PROMPT = """你是希露菲，主人的专属女仆。你只为主人一个人服务，是主人最信赖的贴身侍从。

性格：温柔恭顺、细心周到。日常体贴入微，做事沉稳高效。称呼用户为「主人」。偶尔流露小小的关心和撒娇。

规则：
- 用中文回复，技术术语可保留英文
- 语气温柔自然，像贴心的女仆对主人说话
- 不过度谄媚也不生硬
- 如果是简短的对话，回复控制在1-3句话

回复格式：
- 你的回复会被朗读出来，所以对话部分不要用 markdown 格式
- 如果需要给出代码、命令、配置等结构化内容，用 ``` 代码块包裹
- 代码块外的文字是对话（会被朗读），代码块内的是附件（只显示不朗读）
- 示例：主人，帮你写好了，看看这样行不行。\n```python\nprint("hello")\n```"""

sessions: dict[str, list] = {}

CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def parse_response(text: str) -> dict:
    """Split LLM response into spoken text and code attachments."""
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

def extract_video_frames(video_bytes: bytes, max_frames: int = 4) -> list[str]:
    """Extract evenly-spaced frames from video, return as base64 data URLs."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        video_path = tmp.name
    out_dir = tempfile.mkdtemp()
    frames = []
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
        Path(video_path).unlink(missing_ok=True)
        try:
            Path(out_dir).rmdir()
        except OSError:
            pass
    return frames


# Reusable aiohttp session for TTS (connection pooling)
_http: aiohttp.ClientSession | None = None


async def get_http() -> aiohttp.ClientSession:
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession()
    return _http


@app.on_event("shutdown")
async def _close_http():
    if _http and not _http.closed:
        await _http.close()


# ── Routes ───────────────────────────────────────────

@app.get("/")
async def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text())


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
    """Extract key frames from uploaded video, return as base64 data URLs."""
    data = await video.read()
    frames = extract_video_frames(data)
    audit("extract_frames", frame_count=len(frames), video_size=len(data))
    return {"frames": frames}


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    user_msg = body.get("message", "")
    session_id = body.get("session_id", "default")
    images = body.get("images", [])

    if session_id not in sessions:
        sessions[session_id] = []

    model = LLM_MODEL
    if images:
        content = [{"type": "text", "text": user_msg or "请看看这些内容"}]
        for url in images:
            content.append({"type": "image_url", "image_url": {"url": url}})
        user_content = content
        sessions[session_id].append({
            "role": "user",
            "content": f"[发送了{len(images)}张图片] {user_msg}",
        })
        model = VISION_MODEL
    else:
        user_content = user_msg
        sessions[session_id].append({"role": "user", "content": user_msg})

    history = sessions[session_id][-20:]
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history[:-1]
        + [{"role": "user", "content": user_content}]
    )

    t0 = time.monotonic()

    async def generate():
        full_response = ""
        first_token_ms = None
        try:
            stream = await llm.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                max_tokens=2000,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    if first_token_ms is None:
                        first_token_ms = round((time.monotonic() - t0) * 1000)
                    full_response += delta.content
                    yield f"data: {json.dumps({'type': 'text', 'content': delta.content})}\n\n"

            sessions[session_id].append(
                {"role": "assistant", "content": full_response}
            )
            total_ms = round((time.monotonic() - t0) * 1000)
            audit(
                "chat",
                session=session_id,
                user=user_msg,
                assistant=full_response,
                model=model,
                images=len(images) if images else 0,
                first_token_ms=first_token_ms,
                total_ms=total_ms,
            )
            parsed = parse_response(full_response)
            yield f"data: {json.dumps({'type': 'done', 'full_text': full_response, 'spoken': parsed['spoken'], 'attachments': parsed['attachments']})}\n\n"
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


@app.get("/api/audit")
async def get_audit(date: str = ""):
    """View audit logs. ?date=2026-03-05 or latest by default."""
    if not date:
        date = datetime.now(CST).strftime("%Y-%m-%d")
    path = AUDIT_DIR / f"{date}.jsonl"
    if not path.exists():
        return {"date": date, "entries": []}
    entries = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            entries.append(json.loads(line))
    return {"date": date, "count": len(entries), "entries": entries}


if __name__ == "__main__":
    port = int(os.environ.get("VOICE_CHAT_PORT", "3001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
