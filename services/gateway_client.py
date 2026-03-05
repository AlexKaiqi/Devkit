"""
OpenClaw Gateway WebSocket client for Python services (风铃, Telegram Bot).

Handles Ed25519 device identity, challenge-response handshake,
chat messaging, and streaming agent events.
"""

import asyncio
import hashlib
import json
import logging
import os
import platform
import time
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from pathlib import Path
from typing import Any, AsyncGenerator

import websockets
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

log = logging.getLogger("gateway-client")

PROTOCOL_VERSION = 3
IDENTITY_DIR = Path.home() / ".fengling" / "identity"


def _b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return urlsafe_b64decode(s)


# ── Device identity (Ed25519) ──────────────────────────

class DeviceIdentity:
    """Ed25519 keypair for Gateway device authentication."""

    def __init__(self, device_id: str, public_key_pem: str, private_key_pem: str):
        self.device_id = device_id
        self.public_key_pem = public_key_pem
        self.private_key_pem = private_key_pem

    @staticmethod
    def generate() -> "DeviceIdentity":
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
        priv_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
        raw = public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        # DER SPKI for Ed25519: 12-byte prefix + 32-byte raw key
        raw_key = raw[-32:]
        device_id = hashlib.sha256(raw_key).hexdigest()
        return DeviceIdentity(device_id, pub_pem, priv_pem)

    @staticmethod
    def load_or_create(name: str = "device") -> "DeviceIdentity":
        path = IDENTITY_DIR / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text())
            if data.get("version") == 1:
                return DeviceIdentity(data["deviceId"], data["publicKeyPem"], data["privateKeyPem"])
        identity = DeviceIdentity.generate()
        IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "version": 1,
            "deviceId": identity.device_id,
            "publicKeyPem": identity.public_key_pem,
            "privateKeyPem": identity.private_key_pem,
            "createdAtMs": int(time.time() * 1000),
        }, indent=2) + "\n")
        path.chmod(0o600)
        return identity

    def public_key_raw_b64url(self) -> str:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        pub = load_pem_public_key(self.public_key_pem.encode())
        raw = pub.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        return _b64url(raw[-32:])

    def sign(self, payload: str) -> str:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        key = load_pem_private_key(self.private_key_pem.encode(), password=None)
        sig = key.sign(payload.encode())
        return _b64url(sig)


def _build_v3_payload(
    device_id: str, client_id: str, client_mode: str, role: str,
    scopes: list[str], signed_at_ms: int, token: str | None,
    nonce: str, plat: str, device_family: str = "",
) -> str:
    return "|".join([
        "v3", device_id, client_id, client_mode, role,
        ",".join(scopes), str(signed_at_ms), token or "",
        nonce, plat.lower(), device_family.lower(),
    ])


# ── Gateway Client ─────────────────────────────────────

class GatewayClient:
    """Async WebSocket client for OpenClaw Gateway."""

    def __init__(
        self,
        gateway_url: str = "ws://127.0.0.1:18789",
        token: str = "",
        client_display_name: str = "风铃",
        device_name: str = "device",
        event_bus: Any | None = None,
    ):
        self.gateway_url = gateway_url
        self.token = token
        self.client_id = "gateway-client"
        self.client_display_name = client_display_name
        self.identity = DeviceIdentity.load_or_create(device_name)
        self.ws: websockets.WebSocketClientProtocol | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._event_queues: dict[str, asyncio.Queue] = {}
        self._reader_task: asyncio.Task | None = None
        self._connected = asyncio.Event()
        self._lock = asyncio.Lock()
        self._event_bus = event_bus

    async def connect(self) -> None:
        """Connect to Gateway, perform handshake, then start read loop."""
        self.ws = await websockets.connect(
            self.gateway_url, max_size=10 * 1024 * 1024, proxy=None,
        )

        # 1. Receive challenge (before read loop to avoid recv race)
        raw = await asyncio.wait_for(self.ws.recv(), timeout=10)
        challenge = json.loads(raw)
        if challenge.get("event") != "connect.challenge":
            raise Exception(f"Expected connect.challenge, got {challenge}")
        nonce = challenge["payload"]["nonce"]

        # 2. Build and send connect request
        role = "operator"
        scopes = ["operator.read", "operator.write", "operator.admin"]
        signed_at_ms = int(time.time() * 1000)
        plat = platform.system().lower()

        payload_str = _build_v3_payload(
            device_id=self.identity.device_id,
            client_id=self.client_id,
            client_mode="backend",
            role=role, scopes=scopes,
            signed_at_ms=signed_at_ms,
            token=self.token or None,
            nonce=nonce, plat=plat,
        )
        signature = self.identity.sign(payload_str)

        req_id = str(uuid.uuid4())
        connect_frame = {
            "type": "req",
            "id": req_id,
            "method": "connect",
            "params": {
                "minProtocol": PROTOCOL_VERSION,
                "maxProtocol": PROTOCOL_VERSION,
                "client": {
                    "id": self.client_id,
                    "displayName": self.client_display_name,
                    "version": "1.0.0",
                    "platform": plat,
                    "mode": "backend",
                },
                "role": role,
                "scopes": scopes,
                "caps": [],
                "auth": {"token": self.token} if self.token else {},
                "device": {
                    "id": self.identity.device_id,
                    "publicKey": self.identity.public_key_raw_b64url(),
                    "signature": signature,
                    "signedAt": signed_at_ms,
                    "nonce": nonce,
                },
            },
        }
        await self.ws.send(json.dumps(connect_frame))

        # 3. Wait for connect response (still before read loop)
        raw = await asyncio.wait_for(self.ws.recv(), timeout=10)
        res = json.loads(raw)
        if not res.get("ok"):
            err = res.get("error", {})
            raise Exception(f"Gateway connect failed: {err.get('message', res)}")

        log.info("Gateway connected: protocol=%s", res.get("payload", {}).get("protocol"))

        # 4. Now start background read loop for events
        self._reader_task = asyncio.create_task(self._read_loop())
        self._connected.set()

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self.ws:
            await self.ws.close()
        self._connected.clear()

    def _ws_open(self) -> bool:
        return self.ws is not None and self.ws.close_code is None

    async def ensure_connected(self) -> None:
        if not self._ws_open():
            await self.connect()
        await self._connected.wait()

    async def request(self, method: str, params: dict) -> dict:
        """Send an RPC request, wait for response."""
        req_id = str(uuid.uuid4())
        frame = {"type": "req", "id": req_id, "method": method, "params": params}
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        await self.ws.send(json.dumps(frame))
        return await asyncio.wait_for(future, timeout=30)

    async def resolve_session(self, friendly_id: str = "main") -> str:
        """Resolve a friendly session ID to a session key.

        If the session doesn't exist yet, returns the friendly_id itself;
        Gateway will create it implicitly on first chat.send.
        """
        try:
            result = await self.request("sessions.resolve", {
                "key": friendly_id,
                "includeUnknown": True,
                "includeGlobal": True,
            })
            return result.get("key", friendly_id)
        except Exception as e:
            if "No session found" in str(e):
                log.info("Session '%s' not found, will use as key directly", friendly_id)
                return friendly_id
            raise

    async def chat_send(
        self,
        session_key: str,
        message: str,
        attachments: list[dict] | None = None,
        timeout_ms: int = 120000,
    ) -> AsyncGenerator[dict, None]:
        """
        Send a chat message and yield streaming events.

        Yields dicts with keys:
          - {"type": "text", "content": "..."} — assistant text delta
          - {"type": "tool", "name": "...", "status": "...", "id": "..."} — tool call
          - {"type": "done"} — generation finished
          - {"type": "error", "content": "..."} — error
        """
        await self.ensure_connected()

        queue_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        self._event_queues[queue_id] = queue

        params: dict[str, Any] = {
            "sessionKey": session_key,
            "message": message,
            "deliver": False,
            "timeoutMs": timeout_ms,
            "idempotencyKey": str(uuid.uuid4()),
        }
        if attachments:
            params["attachments"] = attachments

        try:
            result = await self.request("chat.send", params)
        except Exception as e:
            self._event_queues.pop(queue_id, None)
            yield {"type": "error", "content": str(e)}
            return

        run_id = result.get("runId", "")

        full_text = ""
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout_ms / 1000)
                except asyncio.TimeoutError:
                    yield {"type": "error", "content": "Gateway response timeout"}
                    break

                if event is None:
                    break

                evt_payload = event.get("payload", {})
                evt_run_id = evt_payload.get("runId", "")
                if run_id and evt_run_id and evt_run_id != run_id:
                    continue

                evt_name = event.get("event", "")

                if evt_name == "agent":
                    stream_type = evt_payload.get("stream", "")
                    data = evt_payload.get("data", {})

                    if stream_type == "assistant":
                        delta = data.get("delta") or data.get("text") or evt_payload.get("delta") or evt_payload.get("text") or ""
                        if delta:
                            full_text += delta
                            yield {"type": "text", "content": delta}

                    elif stream_type == "tool":
                        yield {
                            "type": "tool",
                            "name": data.get("name") or data.get("toolName") or evt_payload.get("name") or "",
                            "status": data.get("phase") or data.get("status") or evt_payload.get("phase") or "",
                            "id": data.get("id") or data.get("toolCallId") or evt_payload.get("id") or "",
                        }

                    elif stream_type == "lifecycle":
                        phase = data.get("phase") or evt_payload.get("phase") or ""
                        if phase in ("end", "error"):
                            if phase == "error":
                                err = data.get("error") or evt_payload.get("error") or "unknown error"
                                yield {"type": "error", "content": str(err)}
                            yield {"type": "done", "full_text": full_text}
                            break

                elif evt_name == "chat":
                    state = evt_payload.get("state", "")
                    if state == "final":
                        if not full_text:
                            msg = evt_payload.get("message", {})
                            ct = msg.get("content", [])
                            if isinstance(ct, list) and ct:
                                full_text = ct[0].get("text", "")
                            elif isinstance(ct, str):
                                full_text = ct
                        yield {"type": "done", "full_text": full_text}
                        break
        finally:
            self._event_queues.pop(queue_id, None)

    async def chat_abort(self, session_key: str) -> None:
        """Abort an ongoing chat generation."""
        try:
            await self.request("chat.abort", {"sessionKey": session_key})
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────

    async def _read_loop(self) -> None:
        """Background task: route incoming messages to pending futures or event queues."""
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "res":
                    req_id = msg.get("id")
                    future = self._pending.pop(req_id, None)
                    if future and not future.done():
                        if msg.get("ok"):
                            future.set_result(msg.get("payload", {}))
                        else:
                            err = msg.get("error", {})
                            future.set_exception(
                                Exception(err.get("message", "Gateway error"))
                            )

                elif msg_type == "event":
                    evt = msg.get("event", "")
                    if evt in ("agent", "chat"):
                        for q in self._event_queues.values():
                            await q.put(msg)
                    elif evt == "tick":
                        pass

                    if self._event_bus is not None:
                        await self._publish_to_bus(msg)

        except websockets.ConnectionClosed:
            log.warning("Gateway WebSocket closed")
            self._connected.clear()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("Gateway read loop error: %s", e)
            self._connected.clear()
        finally:
            for q in self._event_queues.values():
                await q.put(None)
            for f in self._pending.values():
                if not f.done():
                    f.set_exception(Exception("connection lost"))
            self._pending.clear()

    async def _publish_to_bus(self, msg: dict) -> None:
        """Forward Gateway WebSocket events to the EventBus."""
        try:
            from event_bus import Event
            evt_name = msg.get("event", "")
            payload = msg.get("payload", {})
            session_key = payload.get("sessionKey", "")
            bus_event = Event(
                event_type=f"gateway.{evt_name}",
                session_key=session_key,
                payload=payload,
            )
            await self._event_bus.publish(bus_event)
        except Exception:
            log.debug("EventBus publish failed for gateway event", exc_info=True)
