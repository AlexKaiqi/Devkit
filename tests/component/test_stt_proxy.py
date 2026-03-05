"""L2 Component: STT Proxy health check and audio transcription."""

import struct

import aiohttp
import pytest

STT_BASE = "http://127.0.0.1:8787"


def _make_silent_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a valid WAV file containing silence."""
    num_samples = int(sample_rate * duration_s)
    data_size = num_samples * 2  # 16-bit PCM
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b"data", data_size,
    )
    return header + (b"\x00\x00" * num_samples)


@pytest.mark.requires_stt
class TestSttHealth:

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{STT_BASE}/health") as resp:
                assert resp.status == 200

    @pytest.mark.asyncio
    async def test_root_returns_ok(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(STT_BASE) as resp:
                assert resp.status in (200, 404)


@pytest.mark.requires_stt
class TestSttTranscription:

    @pytest.mark.asyncio
    async def test_silent_audio_returns_text(self):
        wav = _make_silent_wav()
        form = aiohttp.FormData()
        form.add_field("file", wav, filename="test.wav", content_type="audio/wav")
        form.add_field("model", "whisper-1")
        form.add_field("language", "zh")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{STT_BASE}/v1/audio/transcriptions", data=form,
            ) as resp:
                assert resp.status == 200
                result = await resp.json()
                assert "text" in result

    @pytest.mark.asyncio
    async def test_transcription_result_is_string(self):
        wav = _make_silent_wav(0.3)
        form = aiohttp.FormData()
        form.add_field("file", wav, filename="s.wav", content_type="audio/wav")
        form.add_field("model", "whisper-1")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{STT_BASE}/v1/audio/transcriptions", data=form,
            ) as resp:
                result = await resp.json()
                assert isinstance(result.get("text"), str)
