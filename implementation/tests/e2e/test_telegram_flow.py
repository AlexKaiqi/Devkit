"""L4 E2E: Telegram Bot — text/voice/image flow via real bot API."""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

CST = timezone(timedelta(hours=8))
AUDIT_DIR = Path(os.environ.get(
    "AUDIT_DIR",
    Path(__file__).parent.parent.parent / "data" / "voice-audit",
))


@pytest.mark.requires_telegram
class TestTelegramTextFlow:

    @pytest.mark.asyncio
    async def test_send_text_receives_reply(self):
        """Verify Telegram bot responds to text. Requires manual or API-based send."""
        pytest.skip("Requires live Telegram interaction — run manually")

    def test_audit_log_has_req_and_res(self):
        """Check today's audit log for paired req/res entries."""
        today = datetime.now(CST).strftime("%Y-%m-%d")
        log_file = AUDIT_DIR / f"{today}.jsonl"
        if not log_file.exists():
            pytest.skip("No audit log for today")

        entries = [json.loads(l) for l in log_file.read_text().splitlines() if l.strip()]
        req_count = sum(1 for e in entries if e.get("event") == "req")
        res_count = sum(1 for e in entries if e.get("event") == "res")

        assert req_count > 0, "No 'req' entries found in audit log"
        assert res_count > 0, "No 'res' entries found in audit log"
        assert req_count >= res_count, "More res than req — something wrong"


@pytest.mark.requires_telegram
class TestTelegramVoiceFlow:

    @pytest.mark.asyncio
    async def test_voice_message_receives_reply(self):
        pytest.skip("Requires live Telegram voice interaction")


@pytest.mark.requires_telegram
class TestTelegramImageFlow:

    @pytest.mark.asyncio
    async def test_image_message_receives_reply(self):
        pytest.skip("Requires live Telegram image interaction")
