"""L1 Unit: EventBus routing and timer behavior."""

import asyncio

import pytest

from event_bus import EventBus, Event


class TestEventModel:

    def test_event_has_defaults(self):
        event = Event(event_type="timer.fired", session_key="fengling-1")
        assert event.event_type == "timer.fired"
        assert event.session_key == "fengling-1"
        assert isinstance(event.payload, dict)
        assert event.event_id


class TestPublishSubscribe:

    @pytest.mark.asyncio
    async def test_subscribed_handler_receives_event(self):
        bus = EventBus()
        seen: list[Event] = []
        done = asyncio.Event()

        async def handler(event: Event) -> None:
            seen.append(event)
            done.set()

        bus.subscribe("task.resumed", handler)
        await bus.publish(Event(event_type="task.resumed", session_key="fengling-1", payload={"task_id": "t1"}))
        await asyncio.wait_for(done.wait(), timeout=1)

        assert len(seen) == 1
        assert seen[0].payload["task_id"] == "t1"

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_delivery(self):
        bus = EventBus()
        called = False

        async def handler(event: Event) -> None:
            nonlocal called
            called = True

        bus.subscribe("channel.deliver", handler)
        bus.unsubscribe("channel.deliver", handler)
        await bus.publish(Event(event_type="channel.deliver", session_key="tg-1"))
        await asyncio.sleep(0.05)

        assert called is False


class TestTimerScheduling:

    @pytest.mark.asyncio
    async def test_schedule_timer_publishes_timer_fired(self):
        bus = EventBus()
        fired: list[Event] = []
        done = asyncio.Event()

        async def handler(event: Event) -> None:
            fired.append(event)
            done.set()

        bus.subscribe("timer.fired", handler)
        timer_id = await bus.schedule_timer(
            delay_seconds=0.01,
            session_key="tg-123",
            payload={"message": "hello"},
        )

        await asyncio.wait_for(done.wait(), timeout=1)

        assert fired
        assert fired[0].session_key == "tg-123"
        assert fired[0].payload["timer_id"] == timer_id

    @pytest.mark.asyncio
    async def test_cancel_timer_prevents_delivery(self):
        bus = EventBus()
        fired = False

        async def handler(event: Event) -> None:
            nonlocal fired
            fired = True

        bus.subscribe("timer.fired", handler)
        timer_id = await bus.schedule_timer(
            delay_seconds=0.2,
            session_key="tg-123",
            payload={"message": "hello"},
        )
        assert bus.cancel_timer(timer_id) is True

        await asyncio.sleep(0.3)
        assert fired is False

    @pytest.mark.asyncio
    async def test_list_timers_includes_remaining_seconds(self):
        bus = EventBus()
        timer_id = await bus.schedule_timer(
            delay_seconds=0.5,
            session_key="tg-123",
            payload={"message": "hello"},
        )

        timers = bus.list_timers()
        assert timers
        assert timers[0]["id"] == timer_id
        assert "remaining_seconds" in timers[0]

        await bus.shutdown()
