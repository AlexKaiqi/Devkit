"""
Doubao BigModel ASR → OpenAI Whisper API proxy.
Protocol: Volcengine v3/sauc/bigmodel (豆包语音识别大模型)
Reference: livekit-plugins-volcengine/bigmodel_stt.py
"""

import asyncio
import gzip
import json
import os
import struct
import subprocess
import tempfile
import uuid

import logging

import aiohttp
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("doubao-stt")

app = FastAPI()

APPID = os.environ["DOUBAO_APPID"]
TOKEN = os.environ["DOUBAO_TOKEN"]
WS_URL = os.environ.get(
    "DOUBAO_WS_URL", "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
)

PROTOCOL_VERSION = 0b0001
FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111
NO_SEQUENCE = 0b0000
POS_SEQUENCE = 0b0001
NEG_WITH_SEQUENCE = 0b0011
JSON_SERIAL = 0b0001
NO_SERIAL = 0b0000
GZIP_COMPRESS = 0b0001


def _header(msg_type, flags=NO_SEQUENCE, serial=JSON_SERIAL, compress=GZIP_COMPRESS):
    return bytearray([
        (PROTOCOL_VERSION << 4) | 0b0001,
        (msg_type << 4) | flags,
        (serial << 4) | compress,
        0x00,
    ])


def _build_init_request(language="zh-CN"):
    params = {
        "user": {"uid": "stt-proxy"},
        "audio": {
            "format": "pcm",
            "rate": 16000,
            "bits": 16,
            "channels": 1,
            "codec": "raw",
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": False,
            "show_utterance": True,
            "result_type": "single",
            "vad_segment_duration": 15000,
            "end_window_size": 800,
            "force_to_speech_time": 3000,
        },
    }
    payload = gzip.compress(json.dumps(params).encode())
    msg = bytearray(_header(FULL_CLIENT_REQUEST, flags=POS_SEQUENCE))
    msg.extend((1).to_bytes(4, "big", signed=True))  # sequence = 1
    msg.extend(len(payload).to_bytes(4, "big"))
    msg.extend(payload)
    return msg


def _build_audio_chunk(chunk: bytes, seq: int, last=False):
    payload = gzip.compress(chunk)
    flags = NEG_WITH_SEQUENCE if last else POS_SEQUENCE
    wire_seq = -seq if last else seq
    msg = bytearray(_header(AUDIO_ONLY_REQUEST, flags=flags))
    msg.extend(wire_seq.to_bytes(4, "big", signed=True))
    msg.extend(len(payload).to_bytes(4, "big"))
    msg.extend(payload)
    return msg


def _parse_response(data: bytes) -> dict:
    header_size = data[0] & 0x0F
    msg_type = data[1] >> 4
    msg_flags = data[1] & 0x0F
    serial_method = data[2] >> 4
    compression = data[2] & 0x0F
    payload_raw = data[header_size * 4:]
    result = {"type": msg_type, "flags": msg_flags}

    payload_msg = None

    if msg_type == SERVER_FULL_RESPONSE:
        offset = 0
        if msg_flags in (POS_SEQUENCE, NEG_WITH_SEQUENCE):
            seq = int.from_bytes(payload_raw[:4], "big", signed=True)
            result["seq"] = seq
            offset = 4
        if len(payload_raw) >= offset + 4:
            payload_size = int.from_bytes(
                payload_raw[offset:offset + 4], "big", signed=False
            )
            if payload_size > 0 and len(payload_raw) > offset + 4:
                payload_msg = payload_raw[offset + 4:]
    elif msg_type == SERVER_ACK:
        seq = int.from_bytes(payload_raw[:4], "big", signed=True)
        result["seq"] = seq
        if len(payload_raw) >= 8:
            payload_size = int.from_bytes(payload_raw[4:8], "big", signed=False)
            if payload_size > 0 and len(payload_raw) > 8:
                payload_msg = payload_raw[8:]
    elif msg_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload_raw[:4], "big", signed=False)
        result["code"] = code
        if len(payload_raw) >= 8:
            payload_size = int.from_bytes(payload_raw[4:8], "big", signed=False)
            if payload_size > 0 and len(payload_raw) > 8:
                payload_msg = payload_raw[8:]

    if payload_msg and len(payload_msg) > 0:
        try:
            if compression == GZIP_COMPRESS:
                payload_msg = gzip.decompress(payload_msg)
            if serial_method == JSON_SERIAL:
                result["payload"] = json.loads(payload_msg.decode())
        except Exception:
            pass

    return result


def _extract_pcm_from_wav(wav_bytes: bytes) -> bytes:
    if wav_bytes[:4] == b"RIFF":
        offset = 12
        while offset < len(wav_bytes) - 8:
            chunk_id = wav_bytes[offset:offset + 4]
            chunk_size = struct.unpack("<I", wav_bytes[offset + 4:offset + 8])[0]
            if chunk_id == b"data":
                return wav_bytes[offset + 8:offset + 8 + chunk_size]
            offset += 8 + chunk_size
    return wav_bytes


def _convert_to_pcm(audio_bytes: bytes, filename: str = "") -> bytes:
    """Convert any audio format (webm, ogg, mp3, etc.) to 16kHz mono 16-bit PCM via ffmpeg."""
    ext = os.path.splitext(filename)[1].lower() if filename else ""
    if ext in (".wav", ".pcm", "") and audio_bytes[:4] == b"RIFF":
        return _extract_pcm_from_wav(audio_bytes)

    with tempfile.NamedTemporaryFile(suffix=ext or ".webm", delete=False) as src:
        src.write(audio_bytes)
        src_path = src.name
    dst_path = src_path + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src_path,
             "-ar", "16000", "-ac", "1", "-f", "s16le", dst_path],
            capture_output=True, check=True, timeout=30,
        )
        with open(dst_path, "rb") as f:
            return f.read()
    except subprocess.CalledProcessError as e:
        log.error("ffmpeg conversion failed: %s", e.stderr.decode(errors="replace"))
        raise RuntimeError(f"Audio conversion failed: {e.stderr.decode(errors='replace')}")
    finally:
        for p in (src_path, dst_path):
            try:
                os.unlink(p)
            except OSError:
                pass


async def transcribe_with_doubao(audio_bytes: bytes, language: str = "zh-CN", filename: str = "") -> str:
    pcm_data = _convert_to_pcm(audio_bytes, filename)
    reqid = str(uuid.uuid4())

    ws_headers = {
        "X-Api-Resource-Id": "volc.bigasr.sauc.duration",
        "X-Api-Access-Key": TOKEN,
        "X-Api-App-Key": APPID,
        "X-Api-Request-Id": reqid,
    }

    transcript_parts = []

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS_URL, headers=ws_headers) as ws:
            await ws.send_bytes(bytes(_build_init_request(language)))

            chunk_size = 3200  # 100ms at 16kHz 16bit mono
            seq = 2
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i:i + chunk_size]
                is_last = (i + chunk_size) >= len(pcm_data)
                await ws.send_bytes(bytes(_build_audio_chunk(chunk, seq, last=is_last)))
                seq += 1

            while True:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=10.0)
                except asyncio.TimeoutError:
                    break

                if msg.type == aiohttp.WSMsgType.BINARY:
                    resp = _parse_response(msg.data)
                    log.info("recv: %s", {k: v for k, v in resp.items() if k != "payload"})
                    if "payload" in resp:
                        log.info("payload: %s", json.dumps(resp["payload"], ensure_ascii=False)[:500])

                    if resp["type"] == SERVER_ERROR_RESPONSE:
                        raise RuntimeError(f"ASR error: {resp.get('payload', resp.get('code'))}")

                    if "payload" in resp and isinstance(resp["payload"], dict):
                        pm = resp["payload"]
                        r = pm.get("result")
                        if isinstance(r, dict):
                            text = r.get("text", "")
                            utterances = r.get("utterances", [])
                            is_definite = any(u.get("definite") for u in utterances)
                            if text and is_definite:
                                transcript_parts.append(text)
                        elif isinstance(r, list):
                            for item in r:
                                text = item.get("text", "")
                                if text:
                                    transcript_parts.append(text)

                        if resp.get("seq", 1) < 0:
                            break

                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break

    return "".join(transcript_parts) if transcript_parts else ""


@app.post("/v1/audio/transcriptions")
async def whisper_transcriptions(
    file: UploadFile = File(...),
    model: str = Form(default="whisper-1"),
    language: str = Form(default="zh"),
):
    """OpenAI Whisper-compatible transcription endpoint."""
    audio_bytes = await file.read()
    lang_map = {"zh": "zh-CN", "en": "en-US", "ja": "ja-JP", "ko": "ko-KR"}
    lang = lang_map.get(language, language)

    try:
        text = await transcribe_with_doubao(audio_bytes, language=lang, filename=file.filename or "")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return {"text": text}


@app.get("/health")
async def health():
    return {"status": "ok", "provider": "doubao-bigmodel-asr"}


if __name__ == "__main__":
    port = int(os.environ.get("STT_PROXY_PORT", "8787"))
    uvicorn.run(app, host="0.0.0.0", port=port)
