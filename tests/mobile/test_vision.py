"""
视觉理解测试 — 通过 Gemini 测试图片和视频理解能力。

使用 yinli 代理的 OpenAI 兼容接口调用 Gemini 模型，
以 base64 方式传入图片/视频内容。

用法：
    .venv/bin/python tests/mobile/test_vision.py
"""

import base64
import json
import os
import subprocess
import sys
import tempfile

import requests

API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "")
MODEL = os.environ.get("VISION_MODEL", "gemini-2.5-flash-nothinking")

FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Arial Unicode.ttf",
]


def _get_font(size=48):
    from PIL import ImageFont

    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _chat(content_parts: list, max_tokens=300) -> str:
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    r = resp.json()
    if "error" in r:
        raise RuntimeError(f"API error: {r['error']}")
    return r["choices"][0]["message"]["content"]


def _b64(path: str, mime: str) -> str:
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


# ── 图片测试 ──────────────────────────────────────────────


def test_image_basic():
    """基础图片理解：形状 + 颜色 + 文字"""
    from PIL import Image, ImageDraw

    font = _get_font(60)
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    draw.ellipse([50, 30, 350, 270], fill="red")
    draw.text((130, 120), "测试", fill="white", font=font)
    path = os.path.join(tempfile.gettempdir(), "vision_basic.png")
    img.save(path)

    result = _chat([
        {"type": "text", "text": "图片里有什么形状、什么颜色、什么文字？用JSON回答：{shape, color, text}"},
        {"type": "image_url", "image_url": {"url": _b64(path, "image/png")}},
    ])

    ok = "红" in result and "测试" in result
    return ok, result


def test_image_screenshot():
    """截图理解：识别代码内容"""
    from PIL import Image, ImageDraw

    font = _get_font(24)
    img = Image.new("RGB", (600, 200), "#1e1e1e")
    draw = ImageDraw.Draw(img)
    lines = [
        'def hello():',
        '    print("Hello, World!")',
        '',
        'hello()',
    ]
    for i, line in enumerate(lines):
        draw.text((20, 20 + i * 36), line, fill="#d4d4d4", font=font)
    path = os.path.join(tempfile.gettempdir(), "vision_code.png")
    img.save(path)

    result = _chat([
        {"type": "text", "text": "这是一段代码截图，请说明这段代码是什么语言，做了什么事。20字以内。"},
        {"type": "image_url", "image_url": {"url": _b64(path, "image/png")}},
    ])

    ok = "hello" in result.lower() or "打印" in result or "print" in result.lower()
    return ok, result


# ── 视频测试 ──────────────────────────────────────────────


def _make_video(scenes: list[tuple[str, str, str]], fps=10, seconds_per_scene=1) -> str:
    """生成测试视频，返回文件路径。scenes: [(text, bg_color, text_color), ...]"""
    from PIL import Image, ImageDraw

    font = _get_font(56)
    frames_dir = os.path.join(tempfile.gettempdir(), "vision_frames")
    os.makedirs(frames_dir, exist_ok=True)

    idx = 0
    for text, bg, fg in scenes:
        img = Image.new("RGB", (640, 480), bg)
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((640 - tw) // 2, (480 - th) // 2), text, fill=fg, font=font)
        for _ in range(fps * seconds_per_scene):
            img.save(os.path.join(frames_dir, f"f_{idx:04d}.png"))
            idx += 1

    out = os.path.join(tempfile.gettempdir(), "vision_test.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", str(fps),
            "-i", os.path.join(frames_dir, "f_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-t", str(len(scenes) * seconds_per_scene),
            out,
        ],
        check=True, capture_output=True,
    )
    return out


def test_video_scenes():
    """视频理解：识别多个场景的文字和颜色"""
    video = _make_video([
        ("你好世界", "#E53935", "white"),
        ("视频测试", "#43A047", "white"),
        ("第三幕", "#1E88E5", "yellow"),
    ])

    result = _chat([
        {"type": "text", "text": "逐秒描述视频中每个画面的文字内容和背景颜色"},
        {"type": "image_url", "image_url": {"url": _b64(video, "video/mp4")}},
    ])

    ok = "你好" in result and ("视频" in result or "测试" in result) and "三" in result
    return ok, result


def test_video_counting():
    """视频理解：识别数字递增序列"""
    video = _make_video([
        ("1", "#333333", "white"),
        ("2", "#333333", "white"),
        ("3", "#333333", "white"),
        ("4", "#333333", "white"),
        ("5", "#333333", "white"),
    ])

    result = _chat([
        {"type": "text", "text": "视频中依次显示了哪些数字？只列出数字，用逗号分隔。"},
        {"type": "image_url", "image_url": {"url": _b64(video, "video/mp4")}},
    ])

    ok = all(str(n) in result for n in range(1, 6))
    return ok, result


# ── 主入口 ──────────────────────────────────────────────


def main():
    if not API_KEY or not BASE_URL:
        print("需要设置 LLM_API_KEY 和 LLM_BASE_URL 环境变量")
        sys.exit(1)

    print("=" * 50)
    print(f"  视觉理解测试 (model={MODEL})")
    print("=" * 50)

    tests = [
        ("图片 - 形状颜色文字", test_image_basic),
        ("图片 - 代码截图", test_image_screenshot),
        ("视频 - 多场景文字", test_video_scenes),
        ("视频 - 数字序列", test_video_counting),
    ]

    passed = 0
    for name, fn in tests:
        try:
            ok, result = fn()
            status = "✓" if ok else "~"
            if ok:
                passed += 1
            preview = result.replace("\n", " ")[:80]
            print(f"\n  [{status}] {name}")
            print(f"      → {preview}")
        except Exception as e:
            print(f"\n  [✗] {name}")
            print(f"      → {e}")

    print(f"\n{'=' * 50}")
    print(f"  结果: {passed}/{len(tests)} 通过")
    print(f"{'=' * 50}")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
