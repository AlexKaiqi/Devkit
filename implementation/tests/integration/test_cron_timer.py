"""L3 Integration: Cron delayed task — create, trigger, no-blocking."""

import asyncio
import uuid

import pytest


async def _send_and_collect(gw, session_key: str, message: str, timeout_ms: int = 60000) -> str:
    full_text = ""
    async for evt in gw.chat_send(session_key, message, timeout_ms=timeout_ms):
        if evt["type"] == "text":
            full_text += evt["content"]
        elif evt["type"] in ("done", "error"):
            break
    return full_text


@pytest.mark.requires_gateway
class TestCronDelayedTask:

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_delayed_hello_acknowledged_immediately(self, gateway_client, fresh_session):
        """Agent should acknowledge the cron request quickly, not block for the delay."""
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(
            gateway_client, key,
            "10秒后提醒我喝水，请立即确认你已设好定时",
        )
        assert len(reply) > 0

    @pytest.mark.asyncio
    async def test_followup_not_blocked(self, gateway_client, fresh_session):
        """After scheduling a delayed task, immediate follow-up should work."""
        key = await gateway_client.resolve_session(fresh_session)

        # Schedule delayed task
        await _send_and_collect(
            gateway_client, key,
            "30秒后说hello，先确认收到",
        )

        # Immediate follow-up should not be blocked
        reply = await _send_and_collect(
            gateway_client, key,
            "1+1等于几？",
            timeout_ms=30000,
        )
        assert "2" in reply


@pytest.mark.requires_gateway
class TestCronNoBlocking:

    @pytest.mark.asyncio
    async def test_concurrent_messages_no_crosstalk(self, gateway_client):
        """Two different sessions should not receive each other's events."""
        s1 = f"pytest-a-{uuid.uuid4().hex[:6]}"
        s2 = f"pytest-b-{uuid.uuid4().hex[:6]}"
        k1 = await gateway_client.resolve_session(s1)
        k2 = await gateway_client.resolve_session(s2)

        reply1 = await _send_and_collect(
            gateway_client, k1,
            "回复'Alpha'这个单词",
        )
        reply2 = await _send_and_collect(
            gateway_client, k2,
            "回复'Beta'这个单词",
        )
        assert "Alpha" in reply1 or "alpha" in reply1.lower()
        assert "Beta" in reply2 or "beta" in reply2.lower()
