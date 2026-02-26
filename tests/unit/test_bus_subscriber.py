"""Unit tests for agentcore.bus.subscriber.

Tests cover the Subscriber protocol and FilteredSubscriber gating logic.
"""
from __future__ import annotations

import pytest

from agentcore.bus.filters import AgentFilter, TypeFilter
from agentcore.bus.subscriber import FilteredSubscriber, Subscriber
from agentcore.schema.events import AgentEvent, EventType


# ---------------------------------------------------------------------------
# Subscriber protocol
# ---------------------------------------------------------------------------


class TestSubscriberProtocol:
    def test_plain_function_satisfies_protocol(self) -> None:
        def handler(event: AgentEvent) -> None:
            pass

        assert isinstance(handler, Subscriber)

    def test_lambda_satisfies_protocol(self) -> None:
        handler = lambda event: None  # noqa: E731
        assert isinstance(handler, Subscriber)

    def test_list_append_satisfies_protocol(self) -> None:
        received: list[AgentEvent] = []
        assert isinstance(received.append, Subscriber)


# ---------------------------------------------------------------------------
# FilteredSubscriber
# ---------------------------------------------------------------------------


def _make_event(
    event_type: EventType = EventType.CUSTOM, agent_id: str = "agent-1"
) -> AgentEvent:
    return AgentEvent(event_type=event_type, agent_id=agent_id)


class TestFilteredSubscriber:
    def test_forwards_event_when_filter_passes(self) -> None:
        received: list[AgentEvent] = []
        fs = FilteredSubscriber(
            handler=received.append,
            event_filter=TypeFilter(EventType.CUSTOM),
        )
        evt = _make_event(EventType.CUSTOM)
        fs(evt)
        assert len(received) == 1
        assert received[0] is evt

    def test_does_not_forward_when_filter_fails(self) -> None:
        received: list[AgentEvent] = []
        fs = FilteredSubscriber(
            handler=received.append,
            event_filter=TypeFilter(EventType.AGENT_STARTED),
        )
        fs(_make_event(EventType.CUSTOM))
        assert received == []

    def test_returns_handler_result_when_matching(self) -> None:
        results: list[str] = []

        def handler(event: AgentEvent) -> str:
            return "handled"

        fs = FilteredSubscriber(
            handler=handler,
            event_filter=TypeFilter(EventType.CUSTOM),
        )
        result = fs(_make_event(EventType.CUSTOM))
        assert result == "handled"

    def test_returns_none_when_filtered_out(self) -> None:
        fs = FilteredSubscriber(
            handler=lambda e: "handled",
            event_filter=TypeFilter(EventType.AGENT_STARTED),
        )
        result = fs(_make_event(EventType.CUSTOM))
        assert result is None

    def test_compound_filter_and_semantics(self) -> None:
        received: list[AgentEvent] = []
        compound = TypeFilter(EventType.TOOL_CALLED) & AgentFilter("agent-1")
        fs = FilteredSubscriber(handler=received.append, event_filter=compound)

        # Passes both — should be forwarded
        fs(_make_event(EventType.TOOL_CALLED, "agent-1"))
        # Fails agent filter — should be blocked
        fs(_make_event(EventType.TOOL_CALLED, "agent-2"))

        assert len(received) == 1

    def test_repr_contains_handler_and_filter(self) -> None:
        received: list[AgentEvent] = []
        fs = FilteredSubscriber(
            handler=received.append,
            event_filter=TypeFilter(EventType.CUSTOM),
        )
        r = repr(fs)
        assert "FilteredSubscriber" in r
        assert "TypeFilter" in r
