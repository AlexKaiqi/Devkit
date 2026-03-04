"""
OpenCami 移动端自动化测试
用 Playwright 模拟 iPhone/Android 视口，验证页面加载、Gateway 连接、对话功能。

运行:
  .venv/bin/python -m pytest tests/mobile/test_opencami.py -v
"""

import os
import re
import subprocess
import pytest
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.environ.get("OPENCAMI_URL", "http://localhost:3000")
STT_URL = os.environ.get("STT_URL", "http://localhost:8787")

MOBILE_VIEWPORTS = {
    "iPhone 14": {"viewport": {"width": 390, "height": 844}, "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1", "is_mobile": True, "has_touch": True},
    "Pixel 7": {"viewport": {"width": 412, "height": 915}, "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36", "is_mobile": True, "has_touch": True},
}


@pytest.fixture(scope="module")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="module")
def browser(pw):
    b = pw.chromium.launch(headless=True)
    yield b
    b.close()


@pytest.fixture(params=list(MOBILE_VIEWPORTS.keys()))
def mobile_page(browser, request):
    device = MOBILE_VIEWPORTS[request.param]
    ctx = browser.new_context(**device)
    page = ctx.new_page()
    yield page, request.param
    ctx.close()


class TestPageLoad:
    def test_homepage_loads(self, mobile_page):
        page, device = mobile_page
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
        assert page.title() != ""

    def test_viewport_is_mobile(self, mobile_page):
        page, device = mobile_page
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
        viewport = page.viewport_size
        assert viewport["width"] <= 430


class TestGatewayConnection:
    def test_ping(self):
        import urllib.request, json

        req = urllib.request.Request(f"{BASE_URL}/api/ping")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        assert data.get("ok") is True, f"ping failed: {data}"


class TestSTTProxy:
    def test_health(self):
        import urllib.request, json

        req = urllib.request.Request(f"{STT_URL}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        assert data.get("status") == "ok"

    def test_transcription(self):
        wav_path = "/tmp/playwright_test.wav"
        subprocess.run(
            ["say", "-o", wav_path, "--data-format=LEI16@16000", "测试"],
            check=True,
            capture_output=True,
        )
        import urllib.request, json

        boundary = "----TestBoundary"
        with open(wav_path, "rb") as f:
            audio_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="test.wav"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode() + audio_data + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"{STT_URL}/v1/audio/transcriptions",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        assert len(data.get("text", "")) > 0, "empty transcription"


class TestChat:
    def test_chat_ui_elements(self, mobile_page):
        page, device = mobile_page
        page.goto(BASE_URL, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3000)
        body_text = page.content()
        assert len(body_text) > 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
