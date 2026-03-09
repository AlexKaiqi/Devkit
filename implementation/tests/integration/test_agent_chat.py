"""L3 Integration: Agent chat — persona, multi-turn, multilingual."""

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
class TestBasicChat:

    @pytest.mark.asyncio
    async def test_greeting_response(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(gateway_client, key, "你好")
        assert len(reply) > 0

    @pytest.mark.asyncio
    async def test_math_accuracy(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(gateway_client, key, "计算 123 + 456 的结果，只回答数字")
        assert "579" in reply


@pytest.mark.requires_gateway
class TestPersona:

    @pytest.mark.asyncio
    async def test_knows_own_name(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(gateway_client, key, "你叫什么名字？")
        assert "希露菲" in reply or "sylphiette" in reply.lower()

    @pytest.mark.asyncio
    async def test_addresses_master(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(gateway_client, key, "你怎么称呼我？")
        assert "主人" in reply or "master" in reply.lower()


@pytest.mark.requires_gateway
class TestMultiTurn:

    @pytest.mark.asyncio
    async def test_context_retention(self, gateway_client):
        session = f"pytest-multi-{uuid.uuid4().hex[:6]}"
        key = await gateway_client.resolve_session(session)

        await _send_and_collect(gateway_client, key, "请记住数字 42")
        reply = await _send_and_collect(gateway_client, key, "我刚才让你记住的数字是多少？")
        assert "42" in reply


@pytest.mark.requires_gateway
class TestMultilingual:

    @pytest.mark.asyncio
    async def test_english_response(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(gateway_client, key, "Reply in English: What is 2+2?")
        assert "4" in reply

    @pytest.mark.asyncio
    async def test_chinese_response(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        reply = await _send_and_collect(gateway_client, key, "用中文回答：1+1等于几？")
        assert "2" in reply
