"""Unit tests for agentcore.bus.event_bus.EventBus.

Tests cover subscribe, subscribe_all, unsubscribe, emit (async),
emit_sync, history, introspection, and exception safety.
"""
from __future__ import annotations

import asyncio

import pytest

from agentcore.bus.event_bus import EventBus
from agentcore.schema.errors import EventBusError
from agentcore.schema.events import AgentEvent, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus() -> EventBus:
    return EventBus()


def _evt(
    event_type: EventType = EventType.CUSTOM, agent_id: str = "agent-1"
) -> AgentEvent:
    return AgentEvent(event_type=event_type, agent_id=agent_id)


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------


class TestEventBusSubscription:
    def test_subscribe_returns_string_id(self, bus: EventBus) -> None:
        sub_id = bus.subscribe(EventType.CUSTOM, lambda e: None)
        assert isinstance(sub_id, str)
        assert len(sub_id) > 0

    def test_subscribe_all_returns_string_id(self, bus: EventBus) -> None:
        sub_id = bus.subscribe_all(lambda e: None)
        assert isinstance(sub_id, str)

    def test_subscriber_count_increments(self, bus: EventBus) -> None:
        assert bus.subscriber_count() == 0
        bus.subscribe(EventType.CUSTOM, lambda e: None)
        assert bus.subscriber_count() == 1
        bus.subscribe_all(lambda e: None)
        assert bus.subscriber_count() == 2

    def test_unsubscribe_type_subscriber(self, bus: EventBus) -> None:
        sub_id = bus.subscribe(EventType.CUSTOM, lambda e: None)
        bus.unsubscribe(sub_id)
        assert bus.subscriber_count() == 0

    def test_unsubscribe_global_subscriber(self, bus: EventBus) -> None:
        sub_id = bus.subscribe_all(lambda e: None)
        bus.unsubscribe(sub_id)
        assert bus.subscriber_count() == 0

    def test_unsubscribe_unknown_id_raises(self, bus: EventBus) -> None:
        with pytest.raises(EventBusError):
            bus.unsubscribe("non-existent-id")

    def test_subscribe_with_invalid_event_type_raises(self, bus: EventBus) -> None:
        with pytest.raises(EventBusError):
            bus.subscribe("not_an_event_type", lambda e: None)  # type: ignore[arg-type]

    def test_multiple_subscribers_for_same_type(self, bus: EventBus) -> None:
        bus.subscribe(EventType.CUSTOM, lambda e: None)
        bus.subscribe(EventType.CUSTOM, lambda e: None)
        assert bus.subscriber_count() == 2


# ---------------------------------------------------------------------------
# Emission — async
# ---------------------------------------------------------------------------


class TestEventBusEmit:
    async def test_emit_delivers_to_type_subscriber(self, bus: EventBus) -> None:
        received: list[AgentEvent] = []
        bus.subscribe(EventType.AGENT_STARTED, received.append)
        await bus.emit(_evt(EventType.AGENT_STARTED))
        assert len(received) == 1

    async def test_emit_does_not_deliver_to_wrong_type(self, bus: EventBus) -> None:
        received: list[AgentEvent] = []
        bus.subscribe(EventType.AGENT_STOPPED, received.append)
        await bus.emit(_evt(EventType.AGENT_STARTED))
        assert received == []

    async def test_emit_delivers_to_global_subscriber(self, bus: EventBus) -> None:
        received: list[AgentEvent] = []
        bus.subscribe_all(received.append)
        await bus.emit(_evt(EventType.CUSTOM))
        await bus.emit(_evt(EventType.AGENT_STARTED))
        assert len(received) == 2

    async def test_emit_delivers_to_both_type_and_global(
        self, bus: EventBus
    ) -> None:
        type_received: list[AgentEvent] = []
        global_received: list[AgentEvent] = []
        bus.subscribe(EventType.CUSTOM, type_received.append)
        bus.subscribe_all(global_received.append)
        await bus.emit(_evt(EventType.CUSTOM))
        assert len(type_received) == 1
        assert len(global_received) == 1

    async def test_emit_is_exception_safe(self, bus: EventBus) -> None:
        """A misbehaving subscriber must not prevent subsequent ones from receiving."""
        results: list[str] = []

        def bad_handler(event: AgentEvent) -> None:
            raise RuntimeError("subscriber failure")

        def good_handler(event: AgentEvent) -> None:
            results.append("ok")

        bus.subscribe_all(bad_handler)
        bus.subscribe_all(good_handler)
        await bus.emit(_evt())
        assert results == ["ok"]

    async def test_async_subscriber_is_awaited(self, bus: EventBus) -> None:
        received: list[AgentEvent] = []

        async def async_handler(event: AgentEvent) -> None:
            received.append(event)

        bus.subscribe_all(async_handler)
        await bus.emit(_evt())
        assert len(received) == 1

    async def test_emit_adds_to_history(self, bus: EventBus) -> None:
        await bus.emit(_evt())
        assert len(bus.get_history()) == 1


# ---------------------------------------------------------------------------
# Emission — sync wrapper
# ---------------------------------------------------------------------------


class TestEventBusEmitSync:
    def test_emit_sync_delivers_event(self, bus: EventBus) -> None:
        received: list[AgentEvent] = []
        bus.subscribe_all(received.append)
        bus.emit_sync(_evt())
        assert len(received) == 1

    def test_emit_sync_outside_async_context(self, bus: EventBus) -> None:
        received: list[AgentEvent] = []
        bus.subscribe_all(received.append)
        # This runs outside any event loop — must create its own
        bus.emit_sync(_evt(EventType.AGENT_STARTED))
        assert len(received) == 1


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TestEventBusHistory:
    async def test_history_ordered_oldest_first(self, bus: EventBus) -> None:
        evt1 = _evt(EventType.AGENT_STARTED)
        evt2 = _evt(EventType.AGENT_STOPPED)
        await bus.emit(evt1)
        await bus.emit(evt2)
        history = bus.get_history()
        assert history[0].event_id == evt1.event_id
        assert history[1].event_id == evt2.event_id

    async def test_history_is_copy(self, bus: EventBus) -> None:
        await bus.emit(_evt())
        history = bus.get_history()
        history.clear()
        assert len(bus.get_history()) == 1

    async def test_clear_history(self, bus: EventBus) -> None:
        await bus.emit(_evt())
        bus.clear_history()
        assert bus.get_history() == []

    async def test_max_history_limits_buffer(self) -> None:
        small_bus = EventBus(max_history=3)
        for _ in range(5):
            await small_bus.emit(_evt())
        assert len(small_bus.get_history()) == 3

    async def test_max_history_zero_disables_history(self) -> None:
        no_hist_bus = EventBus(max_history=0)
        await no_hist_bus.emit(_evt())
        assert no_hist_bus.get_history() == []


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


class TestEventBusIntrospection:
    def test_repr_contains_subscriber_count(self, bus: EventBus) -> None:
        bus.subscribe_all(lambda e: None)
        r = repr(bus)
        assert "subscribers=1" in r

    def test_repr_contains_history_size(self, bus: EventBus) -> None:
        r = repr(bus)
        assert "history_size" in r
