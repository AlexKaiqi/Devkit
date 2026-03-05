"""L2 Component: GatewayClient connect, handshake, simple RPC."""

import uuid

import pytest


@pytest.mark.requires_gateway
class TestGatewayConnect:

    @pytest.mark.asyncio
    async def test_connect_succeeds(self, gateway_client):
        assert gateway_client.ws is not None
        assert gateway_client._ws_open()

    @pytest.mark.asyncio
    async def test_resolve_session_returns_key(self, gateway_client):
        friendly = f"pytest-{uuid.uuid4().hex[:6]}"
        key = await gateway_client.resolve_session(friendly)
        assert key
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
                pytest.fail(f"Gateway error: {evt['content']}")
        assert len(full_text) > 0

    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self, gateway_token, gateway_port):
        from gateway_client import GatewayClient
        gw = GatewayClient(
            gateway_url=f"ws://127.0.0.1:{gateway_port}",
            token=gateway_token,
            client_display_name="pytest-reconnect",
            device_name="pytest-reconnect",
        )
        await gw.connect()
        assert gw._ws_open()

        await gw.close()
        assert not gw._ws_open()

        await gw.ensure_connected()
        assert gw._ws_open()

        await gw.close()
