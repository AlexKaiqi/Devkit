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

TTS_V1_URL = "https://openspeech.bytedance.com/api/v1/tts"
TTS_V3_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

VOICES_STANDARD = [
    "BV700_V2_streaming",
    "BV001_streaming",
    "BV002_streaming",
]

VOICES_SEEDTTS2 = [
    "zh_female_vv_uranus_bigtts",
    "saturn_zh_female_cancan_tob",
    "zh_male_ruyayichen_saturn_bigtts",
]


def generate_audio_macos(text: str, path: str):
    subprocess.run(
        ["say", "-o", path, "--data-format=LEI16@16000", text],
        check=True, capture_output=True,
    )
    return path


async def tts_v1(text: str, path: str, voice_type: str = "") -> str:
    """标准 TTS (V1 API)，适用于 BV 系列音色"""
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        raise RuntimeError("DOUBAO_APPID/DOUBAO_TOKEN not set")
    if not voice_type:
        voice_type = VOICES_STANDARD[0]

    body = {
        "app": {"appid": DOUBAO_APPID, "token": "access_token", "cluster": "volcano_tts"},
        "user": {"uid": "devkit-test"},
        "audio": {"voice_type": voice_type, "encoding": "wav", "speed_ratio": 1.0},
        "request": {"reqid": uuid.uuid4().hex, "text": text, "text_type": "plain", "operation": "query"},
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer;{DOUBAO_TOKEN}"}

    async with aiohttp.ClientSession() as session:
        async with session.post(TTS_V1_URL, json=body, headers=headers) as resp:
            result = await resp.json()
            if result.get("code") != 3000:
                raise RuntimeError(f"TTS V1 error: {result.get('message', '')}")
            with open(path, "wb") as f:
                f.write(base64.b64decode(result["data"]))
    return path


async def tts_v3(text: str, path: str, speaker: str = "") -> str:
    """SeedTTS 2.0 (V3 API)，适用于 saturn/uranus 系列音色"""
    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        raise RuntimeError("DOUBAO_APPID/DOUBAO_TOKEN not set")
    if not speaker:
        speaker = VOICES_SEEDTTS2[0]

    body = {
        "user": {"uid": "devkit-test"},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": {"format": "wav", "sample_rate": 16000},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Api-App-Id": DOUBAO_APPID,
        "X-Api-Access-Key": DOUBAO_TOKEN,
        "X-Api-Resource-Id": "seed-tts-2.0",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(TTS_V3_URL, json=body, headers=headers) as resp:
            audio = b""
            async for line in resp.content:
                text_line = line.decode().strip()
                if not text_line:
                    continue
                try:
                    j = json.loads(text_line)
                    if j.get("data"):
                        audio += base64.b64decode(j["data"])
                    code = j.get("code", j.get("header", {}).get("code", -1))
                    msg = j.get("message", j.get("header", {}).get("message", ""))
                    if code not in (-1, 0, 20000000):
                        raise RuntimeError(f"TTS V3 error: code={code} {msg}")
                except json.JSONDecodeError:
                    pass
            if not audio:
                raise RuntimeError("TTS V3 returned no audio")
            with open(path, "wb") as f:
                f.write(audio)
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

    if not DOUBAO_APPID or not DOUBAO_TOKEN:
        print("\n  [跳过] 豆包 TTS（DOUBAO_APPID/DOUBAO_TOKEN 未设置）")
    else:
        # 2. 标准 TTS (V1) 闭环
        print("\n── 标准 TTS (V1) → 豆包 STT ──")
        voice = VOICES_STANDARD[0]
        for phrase in test_phrases:
            path = f"/tmp/tts_v1_{hash(phrase) & 0xFFFF}.wav"
            try:
                await tts_v1(phrase, path, voice)
                result = await stt_transcribe(path)
                match = phrase in result.replace("，", "").replace("。", "").replace("？", "")
                status = "✓" if match else "~"
                print(f"  [{status}] \"{phrase}\" → \"{result}\"  (voice={voice})")
            except Exception as e:
                print(f"  [✗] \"{phrase}\" → {e}")

        # 3. SeedTTS 2.0 (V3) 闭环
        print("\n── SeedTTS 2.0 (V3) → 豆包 STT ──")
        speaker = VOICES_SEEDTTS2[0]
        for phrase in test_phrases:
            path = f"/tmp/tts_v3_{hash(phrase) & 0xFFFF}.wav"
            try:
                await tts_v3(phrase, path, speaker)
                result = await stt_transcribe(path)
                match = phrase in result.replace("，", "").replace("。", "").replace("？", "")
                status = "✓" if match else "~"
                print(f"  [{status}] \"{phrase}\" → \"{result}\"  (voice={speaker})")
            except Exception as e:
                print(f"  [✗] \"{phrase}\" → {e}")

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
