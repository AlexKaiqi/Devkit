"""
端到端语音测试：TTS 合成 → STT 识别 → 比对结果
同时支持 macOS say 和豆包 TTS（如果凭据可用）。

运行:
  .venv/bin/python tests/mobile/test_voice_e2e.py
"""

import asyncio
import base64
import json
import os
import subprocess
import uuid

import aiohttp

STT_URL = os.environ.get("STT_URL", "http://localhost:8787")
DOUBAO_APPID = os.environ.get("DOUBAO_APPID", "")
DOUBAO_TOKEN = os.environ.get("DOUBAO_TOKEN", "")
TTS_HTTP_URL = "https://openspeech.bytedance.com/api/v1/tts"

VOICE_TYPES = [
    "BV700_V2_streaming",
    "BV001_streaming",
    "BV002_streaming",
]


def generate_audio_macos(text: str, path: str):
    subprocess.run(
        ["say", "-o", path, "--data-format=LEI16@16000", text],
        check=True, capture_output=True,
    )
    return path


async def generate_audio_doubao(text: str, path: str, voice_type: str = "") -> str:
    """用豆包 TTS HTTP 接口合成语音，返回 WAV 文件路径"""
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        raise RuntimeError("DOUBAO_APPID/DOUBAO_TOKEN not set")

    if not voice_type:
        voice_type = VOICE_TYPES[0]

    request_body = {
        "app": {
            "appid": DOUBAO_APPID,
            "token": "access_token",
            "cluster": "volcano_tts",
        },
        "user": {"uid": "devkit-test"},
        "audio": {
            "voice_type": voice_type,
            "encoding": "wav",
            "speed_ratio": 1.0,
            "volume_ratio": 1.0,
            "pitch_ratio": 1.0,
        },
        "request": {
            "reqid": uuid.uuid4().hex,
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer;{DOUBAO_TOKEN}",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(TTS_HTTP_URL, json=request_body, headers=headers) as resp:
            result = await resp.json()
            code = result.get("code")
            if code != 3000:
                msg = result.get("message", "")
                if "resource not granted" in msg:
                    raise RuntimeError(
                        f"音色 {voice_type} 未授权 (code={code})。"
                        f"可用音色: BV001_streaming, BV002_streaming, BV700_V2_streaming"
                    )
                raise RuntimeError(f"TTS error code={code} msg={msg}")
            audio_b64 = result.get("data", "")
            if not audio_b64:
                raise RuntimeError("TTS returned empty audio data")
            with open(path, "wb") as f:
                f.write(base64.b64decode(audio_b64))

    return path


async def stt_transcribe(audio_path: str) -> str:
    """通过豆包 STT 代理转写音频"""
    data = aiohttp.FormData()
    data.add_field("file", open(audio_path, "rb"), filename="test.wav", content_type="audio/wav")
    data.add_field("model", "whisper-1")
    data.add_field("language", "zh")

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{STT_URL}/v1/audio/transcriptions", data=data) as resp:
            result = await resp.json()
            return result.get("text", "")


async def main():
    test_phrases = [
        "你好世界",
        "帮我查看一下项目状态",
        "今天天气怎么样",
    ]

    print("=" * 50)
    print("  语音端到端测试")
    print("=" * 50)

    # 1. macOS say
    print("\n── macOS TTS → 豆包 STT ──")
    for phrase in test_phrases:
        path = f"/tmp/voice_test_{hash(phrase) & 0xFFFF}.wav"
        generate_audio_macos(phrase, path)
        result = await stt_transcribe(path)
        match = phrase in result.replace("，", "").replace("。", "").replace("？", "")
        status = "✓" if match else "~"
        print(f"  [{status}] \"{phrase}\" → \"{result}\"")

    # 2. 豆包 TTS → 豆包 STT (闭环测试)
    if DOUBAO_APPID and DOUBAO_TOKEN:
        print("\n── 豆包 TTS → 豆包 STT (闭环) ──")
        voice = VOICE_TYPES[0]
        for phrase in test_phrases:
            path = f"/tmp/doubao_tts_{hash(phrase) & 0xFFFF}.wav"
            try:
                await generate_audio_doubao(phrase, path, voice)
                fsize = os.path.getsize(path)
                result = await stt_transcribe(path)
                match = phrase in result.replace("，", "").replace("。", "").replace("？", "")
                status = "✓" if match else "~"
                print(f"  [{status}] \"{phrase}\" → \"{result}\"  ({fsize} bytes, voice={voice})")
            except Exception as e:
                print(f"  [✗] \"{phrase}\" → 错误: {e}")
    else:
        print("\n  [跳过] 豆包 TTS（DOUBAO_APPID/DOUBAO_TOKEN 未设置）")

    # 3. OpenCami STT endpoint
    print("\n── OpenCami STT 集成 ──")
    path = "/tmp/voice_cami_test.wav"
    generate_audio_macos("测试语音输入功能", path)
    try:
        data = aiohttp.FormData()
        data.add_field("audio", open(path, "rb"), filename="test.wav", content_type="audio/wav")
        data.add_field("provider", "openai")
        data.add_field("language", "zh")
        async with aiohttp.ClientSession() as session:
            async with session.post("http://localhost:3000/api/stt", data=data) as resp:
                result = await resp.json()
                if result.get("ok"):
                    print(f"  [✓] OpenCami STT: \"{result.get('text')}\"")
                else:
                    print(f"  [✗] OpenCami STT: {result}")
    except Exception as e:
        print(f"  [✗] OpenCami STT: {e}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
