"""
Lightweight async EventBus with timer scheduling.

Uses Python asyncio primitives — no third-party dependencies.
Events carry a session_key for channel routing (e.g. "tg-6952177147").
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

log = logging.getLogger("event-bus")


@dataclass
class Event:
    event_type: str
    session_key: str
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


HandlerFunc = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async publish/subscribe event bus with built-in timer support."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerFunc]] = {}
        self._timers: dict[str, asyncio.Task] = {}
        self._timer_meta: dict[str, dict] = {}

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

    # ── Timer scheduling ──────────────────────────────

    async def schedule_timer(
        self,
        delay_seconds: float,
        session_key: str,
        payload: dict,
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
        }

        task = asyncio.create_task(self._timer_task(timer_id, delay_seconds, session_key, payload))
        self._timers[timer_id] = task
        log.info(
            "Timer '%s' scheduled: %.1fs, session=%s",
            timer_id, delay_seconds, session_key,
        )
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

    def cancel_timer(self, timer_id: str) -> bool:
        task = self._timers.get(timer_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

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
