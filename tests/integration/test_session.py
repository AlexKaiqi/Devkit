"""L3 Integration: Session management — isolation, concurrency, no-crosstalk."""

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
class TestSessionIsolation:

    @pytest.mark.asyncio
    async def test_different_sessions_isolated(self, gateway_client):
        """Context in session A must not leak to session B."""
        sa = f"pytest-iso-a-{uuid.uuid4().hex[:6]}"
        sb = f"pytest-iso-b-{uuid.uuid4().hex[:6]}"
        ka = await gateway_client.resolve_session(sa)
        kb = await gateway_client.resolve_session(sb)

        await _send_and_collect(gateway_client, ka, "请记住密码是 XRAY42")

        reply_b = await _send_and_collect(
            gateway_client, kb,
            "我之前告诉你的密码是什么？如果不知道就说不知道",
        )
        assert "XRAY42" not in reply_b


@pytest.mark.requires_gateway
class TestSessionConcurrency:

    @pytest.mark.asyncio
    async def test_sequential_messages_correct(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)

        r1 = await _send_and_collect(gateway_client, key, "2+3=?只回答数字")
        r2 = await _send_and_collect(gateway_client, key, "10-7=?只回答数字")

        assert "5" in r1
        assert "3" in r2

    @pytest.mark.asyncio
    async def test_rapid_fire_no_empty_response(self, gateway_client):
        """Quickly sending messages should not result in empty responses."""
        session = f"pytest-rapid-{uuid.uuid4().hex[:6]}"
        key = await gateway_client.resolve_session(session)

        replies = []
        for q in ["1+1=?只回答数字", "2+2=?只回答数字", "3+3=?只回答数字"]:
            r = await _send_and_collect(gateway_client, key, q)
            replies.append(r)

        for r in replies:
            assert len(r) > 0, f"Empty response detected: {replies}"


@pytest.mark.requires_gateway
class TestSessionResolution:

    @pytest.mark.asyncio
    async def test_resolve_same_friendly_id_returns_same_key(self, gateway_client):
        friendly = f"pytest-same-{uuid.uuid4().hex[:6]}"
        k1 = await gateway_client.resolve_session(friendly)
        k2 = await gateway_client.resolve_session(friendly)
        assert k1 == k2

    @pytest.mark.asyncio
    async def test_resolve_different_ids_returns_different_keys(self, gateway_client):
        k1 = await gateway_client.resolve_session(f"pytest-d1-{uuid.uuid4().hex[:6]}")
        k2 = await gateway_client.resolve_session(f"pytest-d2-{uuid.uuid4().hex[:6]}")
        assert k1 != k2
