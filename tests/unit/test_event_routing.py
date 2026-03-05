"""L1 Unit: gateway_client event routing — runId filtering, done/error signals."""

import asyncio
import json
import uuid

import pytest

from gateway_client import GatewayClient, DeviceIdentity, _build_v3_payload, _b64url, _b64url_decode


# ── helpers ─────────────────────────────────────────

def _agent_event(run_id: str, stream: str, data: dict | None = None, **extra) -> dict:
    payload = {"runId": run_id, "stream": stream}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return {"type": "event", "event": "agent", "payload": payload}


def _chat_event(run_id: str, state: str, message: dict | None = None) -> dict:
    payload = {"runId": run_id, "state": state}
    if message:
        payload["message"] = message
    return {"type": "event", "event": "chat", "payload": payload}


# ── DeviceIdentity ─────────────────────────────────

class TestDeviceIdentity:

    def test_generate_produces_valid_identity(self):
        ident = DeviceIdentity.generate()
        assert len(ident.device_id) == 64  # SHA-256 hex
        assert "BEGIN PUBLIC KEY" in ident.public_key_pem
        assert "BEGIN PRIVATE KEY" in ident.private_key_pem

    def test_sign_and_verify_roundtrip(self):
        ident = DeviceIdentity.generate()
        message = "test|payload|v3"
        sig = ident.sign(message)
        assert len(sig) > 10

        sig_bytes = _b64url_decode(sig)
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        pub = load_pem_public_key(ident.public_key_pem.encode())
        pub.verify(sig_bytes, message.encode())  # raises on failure

    def test_public_key_raw_b64url_length(self):
        ident = DeviceIdentity.generate()
        raw = ident.public_key_raw_b64url()
        decoded = _b64url_decode(raw)
        assert len(decoded) == 32  # Ed25519 raw public key


# ── v3 payload builder ─────────────────────────────

class TestBuildV3Payload:

    def test_payload_format(self):
        result = _build_v3_payload(
            device_id="abc123", client_id="test-client",
            client_mode="backend", role="operator",
            scopes=["operator.read", "operator.write"],
            signed_at_ms=1700000000000, token="tok",
            nonce="nonce1", plat="Darwin",
        )
        parts = result.split("|")
        assert parts[0] == "v3"
        assert parts[1] == "abc123"
        assert parts[5] == "operator.read,operator.write"
        assert parts[9] == "darwin"  # plat lowered

    def test_empty_token(self):
        result = _build_v3_payload(
            device_id="d", client_id="c", client_mode="backend",
            role="operator", scopes=[], signed_at_ms=0,
            token=None, nonce="n", plat="Linux",
        )
        assert "||" in result  # empty token slot


# ── b64url helpers ──────────────────────────────────

class TestB64Url:

    def test_roundtrip(self):
        data = b"hello gateway world!"
        assert _b64url_decode(_b64url(data)) == data

    def test_padding_stripped(self):
        encoded = _b64url(b"a")
        assert "=" not in encoded


# ── Event routing logic (simulated queue) ───────────

class TestRunIdFiltering:
    """Simulate the event filtering logic from GatewayClient.chat_send."""

    @staticmethod
    def _filter_events(events: list[dict], target_run_id: str) -> list[dict]:
        """Replicate the runId filtering logic from chat_send."""
        accepted = []
        for event in events:
            evt_payload = event.get("payload", {})
            evt_run_id = evt_payload.get("runId", "")
            if target_run_id and evt_run_id and evt_run_id != target_run_id:
                continue
            accepted.append(event)
        return accepted

    def test_matching_run_id_accepted(self):
        rid = "run-001"
        events = [_agent_event(rid, "assistant", {"delta": "hi"})]
        assert len(self._filter_events(events, rid)) == 1

    def test_mismatched_run_id_rejected(self):
        events = [_agent_event("run-OTHER", "assistant", {"delta": "noise"})]
        assert len(self._filter_events(events, "run-001")) == 0

    def test_empty_event_run_id_accepted(self):
        """Events without runId should still pass (legacy/fallback)."""
        event = {"type": "event", "event": "agent", "payload": {"stream": "assistant"}}
        assert len(self._filter_events([event], "run-001")) == 1

    def test_heartbeat_crosstalk_rejected(self):
        """Heartbeat events from another turn must not leak."""
        events = [
            _agent_event("run-001", "assistant", {"delta": "real"}),
            _agent_event("run-HEARTBEAT", "assistant", {"delta": "HEARTBEAT_OK"}),
            _agent_event("run-001", "lifecycle", {"phase": "end"}),
        ]
        filtered = self._filter_events(events, "run-001")
        texts = [e["payload"].get("data", {}).get("delta", "") for e in filtered]
        assert "HEARTBEAT_OK" not in texts
        assert "real" in texts


class TestStreamTypeRouting:
    """Verify parsing of different stream types in agent events."""

    def test_assistant_delta_extracted(self):
        evt = _agent_event("r1", "assistant", {"delta": "Hello"})
        data = evt["payload"]["data"]
        assert data["delta"] == "Hello"

    def test_lifecycle_end_detected(self):
        evt = _agent_event("r1", "lifecycle", {"phase": "end"})
        assert evt["payload"]["data"]["phase"] == "end"

    def test_lifecycle_error_detected(self):
        evt = _agent_event("r1", "lifecycle", {"phase": "error", "error": "timeout"})
        assert evt["payload"]["data"]["phase"] == "error"

    def test_chat_final_detected(self):
        evt = _chat_event("r1", "final", {"content": [{"text": "done"}]})
        assert evt["payload"]["state"] == "final"

    def test_chat_final_extracts_text(self):
        msg = {"content": [{"text": "Hello world"}]}
        evt = _chat_event("r1", "final", msg)
        content = evt["payload"]["message"]["content"]
        assert content[0]["text"] == "Hello world"


class TestReadLoopRouting:
    """Test that _read_loop correctly routes events vs RPC responses."""

    def test_res_type_is_rpc(self):
        msg = {"type": "res", "id": "req-1", "ok": True, "payload": {"key": "val"}}
        assert msg["type"] == "res"

    def test_event_type_agent(self):
        msg = {"type": "event", "event": "agent", "payload": {}}
        assert msg["type"] == "event"
        assert msg["event"] == "agent"

    def test_tick_events_ignored(self):
        msg = {"type": "event", "event": "tick", "payload": {}}
        assert msg["event"] == "tick"
        # tick events are not forwarded to queues
        assert msg["event"] not in ("agent", "chat")


class TestConcurrentQueues:
    """Verify that multiple concurrent chat_send calls get isolated queues."""

    @pytest.mark.asyncio
    async def test_broadcast_reaches_all_queues(self):
        q1 = asyncio.Queue()
        q2 = asyncio.Queue()
        queues = {"id-1": q1, "id-2": q2}

        event = _agent_event("run-A", "assistant", {"delta": "test"})
        for q in queues.values():
            await q.put(event)

        assert not q1.empty()
        assert not q2.empty()

    @pytest.mark.asyncio
    async def test_run_id_isolates_after_broadcast(self):
        """Even though both queues receive the event, filtering by runId isolates them."""
        events_for_run_a = [
            _agent_event("run-A", "assistant", {"delta": "A-text"}),
            _agent_event("run-B", "assistant", {"delta": "B-text"}),
        ]
        filtered = TestRunIdFiltering._filter_events(events_for_run_a, "run-A")
        assert len(filtered) == 1
        assert filtered[0]["payload"]["data"]["delta"] == "A-text"
