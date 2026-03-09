"""L4 E2E: 风铃 Web client — HTTP API validation."""

import aiohttp
import pytest

FENGLING_BASE = "http://127.0.0.1:3001"


def _fengling_available() -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", 3001)) == 0


@pytest.fixture(autouse=True)
def _skip_if_no_fengling():
    if not _fengling_available():
        pytest.skip("风铃 Web not running on :3001")


class TestFenglingWeb:

    @pytest.mark.asyncio
    async def test_index_returns_html(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(FENGLING_BASE) as resp:
                assert resp.status == 200
                text = await resp.text()
                assert "<html" in text.lower() or "<!doctype" in text.lower()

    @pytest.mark.asyncio
    async def test_static_assets(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(FENGLING_BASE) as resp:
                text = await resp.text()
                assert "script" in text.lower() or "css" in text.lower()
