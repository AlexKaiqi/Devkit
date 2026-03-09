"""L2 Component: LocalAgent session and chat smoke tests."""

import pytest


@pytest.mark.requires_gateway
class TestLocalAgentComponent:

    @pytest.mark.asyncio
    async def test_resolve_session_returns_key(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        assert key == fresh_session
        assert isinstance(key, str)

    @pytest.mark.asyncio
    async def test_simple_chat_returns_text(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        full_text = ""
        async for evt in gateway_client.chat_send(key, "回复OK"):
            if evt["type"] == "text":
                full_text += evt["content"]
            elif evt["type"] == "done":
                break
            elif evt["type"] == "error":
                pytest.fail(f"LocalAgent error: {evt['content']}")
        assert len(full_text) > 0

    @pytest.mark.asyncio
    async def test_same_session_reuses_context(self, gateway_client, fresh_session):
        key = await gateway_client.resolve_session(fresh_session)
        async for _ in gateway_client.chat_send(key, "请记住代号 DEVKIT42"):
            pass

        reply = ""
        async for evt in gateway_client.chat_send(key, "我刚才让你记住的代号是什么？"):
            if evt["type"] == "text":
                reply += evt["content"]
            elif evt["type"] in ("done", "error"):
                break

        assert "DEVKIT42" in reply
