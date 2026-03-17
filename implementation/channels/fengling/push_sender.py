"""
Web Push sender — 管理浏览器订阅并发送推送通知。
文件位置：implementation/channels/fengling/push_sender.py
"""

import asyncio
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("push_sender")

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_SUBS_FILE = _DATA_DIR / "webpush_subscriptions.json"
_VAPID_FILE = _DATA_DIR / "vapid_keys.json"


# ── 订阅持久化 ───────────────────────────────────────────────

def load_subscriptions() -> list[dict]:
    if not _SUBS_FILE.exists():
        return []
    try:
        return json.loads(_SUBS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Failed to load subscriptions: %s", e)
        return []


def _write_subscriptions(subs: list[dict]) -> None:
    _SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SUBS_FILE.write_text(
        json.dumps(subs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_subscription(sub: dict) -> None:
    """保存新订阅，按 endpoint 去重。"""
    subs = load_subscriptions()
    endpoint = sub.get("endpoint", "")
    # 去重：移除同 endpoint 的旧记录
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    subs.append(sub)
    _write_subscriptions(subs)
    log.info("Subscription saved, total=%d", len(subs))


def remove_subscription(endpoint: str) -> None:
    """移除指定 endpoint 的订阅。"""
    subs = load_subscriptions()
    before = len(subs)
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    if len(subs) < before:
        _write_subscriptions(subs)
        log.info("Subscription removed, total=%d", len(subs))


# ── VAPID ────────────────────────────────────────────────────

def get_vapid_public_key() -> str | None:
    if not _VAPID_FILE.exists():
        return None
    try:
        data = json.loads(_VAPID_FILE.read_text(encoding="utf-8"))
        return data.get("public_key_b64")
    except Exception as e:
        log.warning("Failed to read VAPID keys: %s", e)
        return None


def _get_vapid_private_key() -> str | None:
    if not _VAPID_FILE.exists():
        return None
    try:
        data = json.loads(_VAPID_FILE.read_text(encoding="utf-8"))
        return data.get("private_key")
    except Exception:
        return None


# ── 推送发送 ─────────────────────────────────────────────────

def _send_one(sub: dict, title: str, body: str) -> None:
    """同步发送单条推送（在 executor 中运行）。"""
    from pywebpush import webpush, WebPushException  # type: ignore

    vapid_private = _get_vapid_private_key()
    if not vapid_private:
        raise RuntimeError("VAPID private key not found")

    payload = json.dumps({"title": title, "body": body, "url": "/"})
    vapid_claims = {
        "sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@localhost")
    }

    webpush(
        subscription_info=sub,
        data=payload,
        vapid_private_key=vapid_private,
        vapid_claims=vapid_claims,
    )


async def send_all(title: str, body: str) -> dict:
    """并发推送所有订阅，自动清理 404/410 过期订阅。返回 {sent, failed}。"""
    from pywebpush import WebPushException  # type: ignore

    subs = load_subscriptions()
    if not subs:
        return {"sent": 0, "failed": 0}

    loop = asyncio.get_event_loop()
    sent = 0
    failed = 0
    expired_endpoints: list[str] = []

    async def _push(sub: dict) -> None:
        nonlocal sent, failed
        try:
            await loop.run_in_executor(None, _send_one, sub, title, body)
            sent += 1
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else 0
            if status in (404, 410):
                expired_endpoints.append(sub.get("endpoint", ""))
                log.info("Subscription expired (HTTP %s), will remove", status)
            else:
                log.warning("WebPushException: %s", e)
                failed += 1
        except Exception as e:
            log.warning("Push failed: %s", e)
            failed += 1

    await asyncio.gather(*[_push(s) for s in subs])

    # 清理过期订阅
    for ep in expired_endpoints:
        remove_subscription(ep)

    log.info("Web Push sent=%d failed=%d expired=%d", sent, failed, len(expired_endpoints))
    return {"sent": sent, "failed": failed}
