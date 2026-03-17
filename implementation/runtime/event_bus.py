"""
Lightweight async EventBus with timer scheduling.

Uses Python asyncio primitives — no third-party dependencies.
Events carry a session_key for channel routing (e.g. "tg-6952177147").
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Coroutine

log = logging.getLogger("event-bus")

_CST = timezone(timedelta(hours=8))


@dataclass
class Event:
    event_type: str
    session_key: str
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


HandlerFunc = Callable[[Event], Coroutine[Any, Any, None]]


def _cron_next_delay(cron_expr: str) -> float:
    """Return seconds until the next cron firing (CST timezone)."""
    from croniter import croniter
    now_cst = datetime.now(_CST)
    c = croniter(cron_expr, now_cst)
    nxt: datetime = c.get_next(datetime)
    return max(1.0, (nxt - now_cst).total_seconds())


class EventBus:
    """Async publish/subscribe event bus with built-in timer support."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._handlers: dict[str, list[HandlerFunc]] = {}
        self._timers: dict[str, asyncio.Task] = {}
        self._timer_meta: dict[str, dict] = {}
        self._persist_path = persist_path

    def subscribe(self, event_type: str, handler: HandlerFunc) -> None:
        self._handlers.setdefault(event_type, []).append(handler)
        log.debug("Subscribed handler to '%s'", event_type)

    def unsubscribe(self, event_type: str, handler: HandlerFunc) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            log.debug("No handlers for event '%s'", event.event_type)
            return
        for handler in handlers:
            asyncio.create_task(self._safe_call(handler, event))

    async def _safe_call(self, handler: HandlerFunc, event: Event) -> None:
        try:
            await handler(event)
        except Exception:
            log.exception(
                "Handler %s failed for event %s",
                handler.__name__, event.event_type,
            )

    # ── One-shot timer ────────────────────────────────

    async def schedule_timer(
        self,
        delay_seconds: float,
        session_key: str,
        payload: dict,
        intent: dict | None = None,
    ) -> str:
        timer_id = str(uuid.uuid4())
        fire_at = time.time() + delay_seconds

        self._timer_meta[timer_id] = {
            "id": timer_id,
            "session_key": session_key,
            "delay_seconds": delay_seconds,
            "fire_at": fire_at,
            "created_at": time.time(),
            "payload": payload,
            "type": "once",
            "intent": intent if intent is not None else {"type": "once"},
        }

        task = asyncio.create_task(self._timer_task(timer_id, delay_seconds, session_key, payload))
        self._timers[timer_id] = task
        self._persist()
        log.info("Timer '%s' scheduled: %.1fs, session=%s", timer_id, delay_seconds, session_key)
        return timer_id

    async def _timer_task(
        self,
        timer_id: str,
        delay: float,
        session_key: str,
        payload: dict,
    ) -> None:
        try:
            await asyncio.sleep(delay)
            event = Event(
                event_type="timer.fired",
                session_key=session_key,
                payload={**payload, "timer_id": timer_id},
            )
            log.info("Timer '%s' fired for session=%s", timer_id, session_key)
            await self.publish(event)
        except asyncio.CancelledError:
            log.info("Timer '%s' cancelled", timer_id)
        finally:
            self._timers.pop(timer_id, None)
            self._timer_meta.pop(timer_id, None)
            self._persist()

    # ── Cron (periodic) timer ─────────────────────────

    async def schedule_cron(
        self,
        cron_expr: str,
        session_key: str,
        payload: dict,
        label: str = "",
        intent: dict | None = None,
    ) -> str:
        """Schedule a recurring reminder using a cron expression (CST).

        cron_expr: standard 5-field cron, e.g. '0 9 * * 1-5' (weekdays 09:00 CST)
        Returns timer_id that can be used to cancel.
        """
        # Validate cron expression
        try:
            from croniter import croniter
            if not croniter.is_valid(cron_expr):
                raise ValueError(f"Invalid cron expression: {cron_expr!r}")
        except ImportError:
            raise RuntimeError("croniter not installed")

        timer_id = str(uuid.uuid4())
        delay = _cron_next_delay(cron_expr)
        fire_at = time.time() + delay

        self._timer_meta[timer_id] = {
            "id": timer_id,
            "session_key": session_key,
            "fire_at": fire_at,
            "created_at": time.time(),
            "payload": payload,
            "type": "cron",
            "cron_expr": cron_expr,
            "label": label or cron_expr,
            "intent": intent if intent is not None else {"type": "recurring"},
        }

        task = asyncio.create_task(self._cron_task(timer_id, cron_expr, session_key, payload))
        self._timers[timer_id] = task
        self._persist()
        next_cst = datetime.now(_CST) + timedelta(seconds=delay)
        log.info(
            "Cron timer '%s' scheduled: '%s', next=%s, session=%s",
            timer_id, cron_expr, next_cst.strftime("%Y-%m-%d %H:%M"), session_key,
        )
        return timer_id

    async def _cron_task(
        self,
        timer_id: str,
        cron_expr: str,
        session_key: str,
        payload: dict,
    ) -> None:
        """Loop: sleep until next cron time, fire, repeat."""
        try:
            while True:
                try:
                    delay = _cron_next_delay(cron_expr)
                except Exception:
                    log.exception("Cron timer '%s': failed to compute next delay for '%s', retrying in 60s", timer_id, cron_expr)
                    await asyncio.sleep(60)
                    continue
                fire_at = time.time() + delay
                # Update fire_at in meta so list_timers shows correct next time
                if timer_id in self._timer_meta:
                    self._timer_meta[timer_id]["fire_at"] = fire_at
                    self._persist()

                await asyncio.sleep(delay)

                event = Event(
                    event_type="timer.fired",
                    session_key=session_key,
                    payload={**payload, "timer_id": timer_id},
                )
                log.info("Cron timer '%s' fired for session=%s", timer_id, session_key)
                try:
                    await self.publish(event)
                except Exception:
                    log.exception("Cron timer '%s': publish failed, continuing loop", timer_id)

        except asyncio.CancelledError:
            log.info("Cron timer '%s' cancelled", timer_id)
        finally:
            self._timers.pop(timer_id, None)
            self._timer_meta.pop(timer_id, None)
            self._persist()

    # ── Cancel ────────────────────────────────────────

    def cancel_timer(self, timer_id: str) -> bool:
        task = self._timers.get(timer_id)
        if task and not task.done():
            task.cancel()
            self._timers.pop(timer_id, None)
            self._timer_meta.pop(timer_id, None)
            self._persist()
            return True
        return False

    # ── Persistence ───────────────────────────────────

    def _persist(self) -> None:
        """Write current timer_meta to persist_path (if configured)."""
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            entries = []
            for meta in self._timer_meta.values():
                entry = {
                    "id": meta["id"],
                    "session_key": meta["session_key"],
                    "fire_at": meta["fire_at"],
                    "payload": meta["payload"],
                    "type": meta.get("type", "once"),
                    "intent": meta.get("intent", {"type": meta.get("type", "once")} if meta.get("type") != "cron" else {"type": "recurring"}),
                }
                if meta.get("type") == "cron":
                    entry["cron_expr"] = meta["cron_expr"]
                    entry["label"] = meta.get("label", "")
                entries.append(entry)
            self._persist_path.write_text(json.dumps(entries, ensure_ascii=False))
        except Exception:
            log.exception("Failed to persist timers")

    async def restore_timers(self) -> None:
        """Read persist_path and reschedule timers that haven't fired yet."""
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            entries = json.loads(self._persist_path.read_text())
        except Exception:
            log.warning("Failed to read timers persist file")
            return

        now = time.time()
        restored = 0
        for entry in entries:
            timer_id = entry.get("id", "")
            fire_at = entry.get("fire_at", 0)
            session_key = entry.get("session_key", "")
            if not session_key:
                log.warning(
                    "Restored timer %s has no session_key — delivery may fail; "
                    "consider recreating this reminder",
                    timer_id,
                )
            payload = entry.get("payload", {})
            timer_type = entry.get("type", "once")
            cron_expr = entry.get("cron_expr", "")

            if timer_type == "cron":
                # Cron timers always restore (they recur)
                self._timer_meta[timer_id] = {
                    "id": timer_id,
                    "session_key": session_key,
                    "fire_at": time.time() + _cron_next_delay(cron_expr),
                    "created_at": now,
                    "payload": payload,
                    "type": "cron",
                    "cron_expr": cron_expr,
                    "label": entry.get("label", cron_expr),
                    "intent": entry.get("intent", {"type": "recurring"}),
                }
                task = asyncio.create_task(
                    self._cron_task(timer_id, cron_expr, session_key, payload)
                )
                self._timers[timer_id] = task
                restored += 1
                log.info("Restored cron timer %s: '%s'", timer_id, cron_expr)
            else:
                if fire_at <= now - 60:  # 超过 60 秒前已过期则跳过；60 秒内立即补发
                    log.info("Skipping expired timer %s (expired %.1fs ago)", timer_id, now - fire_at)
                    continue
                delay = max(fire_at - now, 0)  # 窗口内过期的立即触发
                self._timer_meta[timer_id] = {
                    "id": timer_id,
                    "session_key": session_key,
                    "delay_seconds": delay,
                    "fire_at": fire_at,
                    "created_at": now,
                    "payload": payload,
                    "type": "once",
                    "intent": entry.get("intent", {"type": "once"}),
                }
                task = asyncio.create_task(self._timer_task(timer_id, delay, session_key, payload))
                self._timers[timer_id] = task
                restored += 1
                log.info("Restored timer %s: fires in %.1fs", timer_id, delay)

        if restored:
            log.info("Restored %d timers from persist file", restored)

    def list_timers(self) -> list[dict]:
        now = time.time()
        result = []
        for tid, meta in self._timer_meta.items():
            remaining = max(0, meta["fire_at"] - now)
            result.append({**meta, "remaining_seconds": round(remaining, 1)})
        return result

    async def shutdown(self) -> None:
        for task in self._timers.values():
            task.cancel()
        if self._timers:
            await asyncio.gather(*self._timers.values(), return_exceptions=True)
        self._timers.clear()
        self._timer_meta.clear()
        log.info("EventBus shut down, all timers cancelled")
