"""L2 Component: Doubao TTS API — synthesis and format validation."""

import base64
import os
import uuid

import aiohttp
import pytest

DOUBAO_TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"


def _tts_payload(text: str, voice: str = "zh_female_tianmeixiaoyuan_moon_bigtts") -> dict:
    return {
        "app": {
            "appid": os.environ.get("DOUBAO_APPID", ""),
            "token": "access_token",
            "cluster": "volcano_tts",
        },
        "user": {"uid": "pytest"},
        "audio": {"voice_type": voice, "encoding": "mp3", "speed_ratio": 1.0},
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "operation": "query",
        },
    }


@pytest.mark.requires_tts
class TestTtsSynthesis:

    @pytest.mark.asyncio
    async def test_short_chinese_text(self):
        payload = _tts_payload("你好主人")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DOUBAO_TTS_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer; {os.environ['DOUBAO_TOKEN']}",
                },
                json=payload,
            ) as resp:
                result = await resp.json()
                assert result["code"] == 3000, f"TTS error: {result.get('message')}"
                audio = base64.b64decode(result["data"])
                assert len(audio) > 100

    @pytest.mark.asyncio
    async def test_short_english_text(self):
        payload = _tts_payload("Hello, how are you?")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DOUBAO_TTS_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer; {os.environ['DOUBAO_TOKEN']}",
                },
                json=payload,
            ) as resp:
                result = await resp.json()
                assert result["code"] == 3000

    @pytest.mark.asyncio
    async def test_invalid_voice_type_errors(self):
        payload = _tts_payload("test", voice="nonexistent_voice_xyz")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DOUBAO_TTS_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer; {os.environ['DOUBAO_TOKEN']}",
                },
                json=payload,
            ) as resp:
                result = await resp.json()
                assert result["code"] != 3000

    @pytest.mark.asyncio
    async def test_audio_is_valid_mp3(self):
        payload = _tts_payload("测试音频格式")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DOUBAO_TTS_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer; {os.environ['DOUBAO_TOKEN']}",
                },
                json=payload,
            ) as resp:
                result = await resp.json()
                if result["code"] == 3000:
                    audio = base64.b64decode(result["data"])
                    # MP3 frames start with 0xFF 0xFB/0xF3/0xF2 sync word
                    assert audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3")
