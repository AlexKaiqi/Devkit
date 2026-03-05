"""Shared fixtures and skip conditions for Devkit test suite."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest

DEVKIT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(DEVKIT_ROOT / "services"))

collect_ignore = ["mobile"]

# ── .env loading ──────────────────────────────────────

def _load_dotenv():
    env_path = DEVKIT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

_load_dotenv()

# ── Skip helpers ──────────────────────────────────────

def _port_open(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0

def _gateway_available() -> bool:
    port = int(os.environ.get("OPENCLAW_GATEWAY_PORT", "18789"))
    return _port_open(port)

def _stt_available() -> bool:
    return _port_open(int(os.environ.get("STT_PROXY_PORT", "8787")))

def _tts_configured() -> bool:
    return bool(os.environ.get("DOUBAO_APPID")) and bool(os.environ.get("DOUBAO_TOKEN"))

def _telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN"))

# ── Auto-skip by marker ──────────────────────────────

def pytest_collection_modifyitems(config, items):
    checks = {
        "requires_gateway": (_gateway_available, "Gateway not running"),
        "requires_stt": (_stt_available, "STT Proxy not running"),
        "requires_tts": (_tts_configured, "DOUBAO_APPID/TOKEN not set"),
        "requires_telegram": (_telegram_configured, "TELEGRAM_BOT_TOKEN not set"),
    }
    for item in items:
        for marker_name, (check_fn, reason) in checks.items():
            if marker_name in [m.name for m in item.iter_markers()]:
                if not check_fn():
                    item.add_marker(pytest.mark.skip(reason=reason))

# ── Fixtures ──────────────────────────────────────────

@pytest.fixture(scope="session")
def gateway_token() -> str:
    return os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

@pytest.fixture(scope="session")
def gateway_port() -> int:
    return int(os.environ.get("OPENCLAW_GATEWAY_PORT", "18789"))

@pytest.fixture(scope="session")
async def gateway_client(gateway_token, gateway_port):
    from gateway_client import GatewayClient
    gw = GatewayClient(
        gateway_url=f"ws://127.0.0.1:{gateway_port}",
        token=gateway_token,
        client_display_name="pytest",
        device_name="pytest-runner",
    )
    await gw.connect()
    yield gw
    await gw.close()

@pytest.fixture
def fresh_session() -> str:
    return f"pytest-{uuid.uuid4().hex[:8]}"
