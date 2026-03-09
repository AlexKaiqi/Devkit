"""L3 Integration: Voice pipeline — STT -> Agent -> TTS end-to-end."""

import struct

import aiohttp
import pytest


def _make_silent_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    num_samples = int(sample_rate * duration_s)
    data_size = num_samples * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b"data", data_size,
    )
    return header + (b"\x00\x00" * num_samples)


@pytest.mark.requires_stt
@pytest.mark.requires_tts
@pytest.mark.requires_gateway
class TestVoicePipeline:

    @pytest.mark.asyncio
    async def test_stt_produces_text(self):
        wav = _make_silent_wav(1.0)
        form = aiohttp.FormData()
        form.add_field("file", wav, filename="test.wav", content_type="audio/wav")
        form.add_field("model", "whisper-1")
        form.add_field("language", "zh")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://127.0.0.1:8787/v1/audio/transcriptions", data=form,
            ) as resp:
                result = await resp.json()
                assert "text" in result

    @pytest.mark.asyncio
    async def test_agent_then_tts(self, gateway_client, fresh_session):
        """Send text to agent, then synthesize the reply via TTS."""
        import base64
        import os
        import uuid

        key = await gateway_client.resolve_session(fresh_session)
        full_text = ""
        async for evt in gateway_client.chat_send(key, "用一句话介绍你自己"):
            if evt["type"] == "text":
                full_text += evt["content"]
            elif evt["type"] in ("done", "error"):
                break

        assert len(full_text) > 0

        tts_payload = {
            "app": {
                "appid": os.environ.get("DOUBAO_APPID", ""),
                "token": "access_token",
                "cluster": "volcano_tts",
            },
            "user": {"uid": "pytest"},
            "audio": {
                "voice_type": "zh_female_tianmeixiaoyuan_moon_bigtts",
                "encoding": "mp3",
                "speed_ratio": 1.0,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": full_text[:200],
                "operation": "query",
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openspeech.bytedance.com/api/v1/tts",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer; {os.environ['DOUBAO_TOKEN']}",
                },
                json=tts_payload,
            ) as resp:
                result = await resp.json()
                assert result["code"] == 3000
                audio = base64.b64decode(result["data"])
                assert len(audio) > 100
