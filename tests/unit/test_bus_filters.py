"""Unit tests for agentcore.bus.filters.

Tests cover TypeFilter, AgentFilter, MetadataFilter, CompositeFilter,
and the operator shortcuts (& / |).
"""
from __future__ import annotations

import pytest

from agentcore.bus.filters import (
    AgentFilter,
    CompositeFilter,
    EventFilter,
    FilterMode,
    MetadataFilter,
    TypeFilter,
)
from agentcore.schema.events import AgentEvent, EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_event(
    event_type: EventType = EventType.CUSTOM,
    agent_id: str = "agent-1",
    metadata: dict[str, object] | None = None,
) -> AgentEvent:
    return AgentEvent(
        event_type=event_type,
        agent_id=agent_id,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# FilterMode
# ---------------------------------------------------------------------------


class TestFilterMode:
    def test_all_and_any_values(self) -> None:
        assert FilterMode.ALL.value == "all"
        assert FilterMode.ANY.value == "any"


# ---------------------------------------------------------------------------
# TypeFilter
# ---------------------------------------------------------------------------


class TestTypeFilter:
    def test_matches_included_type(self) -> None:
        f = TypeFilter(EventType.AGENT_STARTED)
        evt = make_event(event_type=EventType.AGENT_STARTED)
        assert f.matches(evt) is True

    def test_rejects_excluded_type(self) -> None:
        f = TypeFilter(EventType.AGENT_STARTED)
        evt = make_event(event_type=EventType.AGENT_STOPPED)
        assert f.matches(evt) is False

    def test_accepts_multiple_types(self) -> None:
        f = TypeFilter(EventType.TOOL_CALLED, EventType.TOOL_COMPLETED)
        assert f.matches(make_event(EventType.TOOL_CALLED)) is True
        assert f.matches(make_event(EventType.TOOL_COMPLETED)) is True
        assert f.matches(make_event(EventType.TOOL_FAILED)) is False

    def test_repr_contains_type_values(self) -> None:
        f = TypeFilter(EventType.AGENT_STARTED)
        assert "agent_started" in repr(f)

    def test_is_event_filter_subclass(self) -> None:
        f = TypeFilter(EventType.CUSTOM)
        assert isinstance(f, EventFilter)


# ---------------------------------------------------------------------------
# AgentFilter
# ---------------------------------------------------------------------------


class TestAgentFilter:
    def test_matches_included_agent(self) -> None:
        f = AgentFilter("agent-1")
        evt = make_event(agent_id="agent-1")
        assert f.matches(evt) is True

    def test_rejects_excluded_agent(self) -> None:
        f = AgentFilter("agent-1")
        evt = make_event(agent_id="agent-2")
        assert f.matches(evt) is False

    def test_accepts_multiple_agent_ids(self) -> None:
        f = AgentFilter("a1", "a2", "a3")
        assert f.matches(make_event(agent_id="a1")) is True
        assert f.matches(make_event(agent_id="a2")) is True
        assert f.matches(make_event(agent_id="a3")) is True
        assert f.matches(make_event(agent_id="a4")) is False

    def test_repr_contains_agent_ids(self) -> None:
        f = AgentFilter("my-agent")
        assert "my-agent" in repr(f)

    def test_is_event_filter_subclass(self) -> None:
        assert isinstance(AgentFilter("x"), EventFilter)


# ---------------------------------------------------------------------------
# MetadataFilter
# ---------------------------------------------------------------------------


class TestMetadataFilter:
    def test_matches_when_key_value_present(self) -> None:
        f = MetadataFilter("env", "prod")
        evt = make_event(metadata={"env": "prod"})
        assert f.matches(evt) is True

    def test_rejects_when_key_absent(self) -> None:
        f = MetadataFilter("env", "prod")
        evt = make_event(metadata={"region": "us-east"})
        assert f.matches(evt) is False

    def test_rejects_when_value_differs(self) -> None:
        f = MetadataFilter("env", "prod")
        evt = make_event(metadata={"env": "staging"})
        assert f.matches(evt) is False

    def test_repr_contains_key_and_value(self) -> None:
        f = MetadataFilter("env", "prod")
        assert "env" in repr(f)
        assert "prod" in repr(f)

    def test_is_event_filter_subclass(self) -> None:
        assert isinstance(MetadataFilter("k", "v"), EventFilter)


# ---------------------------------------------------------------------------
# CompositeFilter
# ---------------------------------------------------------------------------


class TestCompositeFilter:
    def test_all_mode_passes_when_all_match(self) -> None:
        f = CompositeFilter(
            [TypeFilter(EventType.CUSTOM), AgentFilter("agent-1")],
            mode=FilterMode.ALL,
        )
        evt = make_event(EventType.CUSTOM, "agent-1")
        assert f.matches(evt) is True

    def test_all_mode_fails_when_one_fails(self) -> None:
        f = CompositeFilter(
            [TypeFilter(EventType.CUSTOM), AgentFilter("agent-1")],
            mode=FilterMode.ALL,
        )
        evt = make_event(EventType.AGENT_STARTED, "agent-1")
        assert f.matches(evt) is False

    def test_any_mode_passes_when_one_matches(self) -> None:
        f = CompositeFilter(
            [TypeFilter(EventType.AGENT_STARTED), AgentFilter("agent-1")],
            mode=FilterMode.ANY,
        )
        evt = make_event(EventType.CUSTOM, "agent-1")
        assert f.matches(evt) is True

    def test_any_mode_fails_when_none_match(self) -> None:
        f = CompositeFilter(
            [TypeFilter(EventType.AGENT_STARTED), AgentFilter("agent-1")],
            mode=FilterMode.ANY,
        )
        evt = make_event(EventType.CUSTOM, "agent-99")
        assert f.matches(evt) is False

    def test_default_mode_is_all(self) -> None:
        f = CompositeFilter([TypeFilter(EventType.CUSTOM)])
        assert f._mode is FilterMode.ALL

    def test_repr_contains_and_for_all_mode(self) -> None:
        f = CompositeFilter(
            [TypeFilter(EventType.CUSTOM), AgentFilter("agent-1")],
            mode=FilterMode.ALL,
        )
        assert "AND" in repr(f)

    def test_repr_contains_or_for_any_mode(self) -> None:
        f = CompositeFilter(
            [TypeFilter(EventType.CUSTOM), AgentFilter("agent-1")],
            mode=FilterMode.ANY,
        )
        assert "OR" in repr(f)


# ---------------------------------------------------------------------------
# Operator shortcuts
# ---------------------------------------------------------------------------


class TestFilterOperators:
    def test_and_operator_creates_composite_all(self) -> None:
        f = TypeFilter(EventType.TOOL_CALLED) & AgentFilter("agent-1")
        assert isinstance(f, CompositeFilter)
        assert f._mode is FilterMode.ALL

    def test_or_operator_creates_composite_any(self) -> None:
        f = TypeFilter(EventType.TOOL_CALLED) | AgentFilter("agent-1")
        assert isinstance(f, CompositeFilter)
        assert f._mode is FilterMode.ANY

    def test_and_compound_filter_matches_correctly(self) -> None:
        f = TypeFilter(EventType.TOOL_CALLED) & AgentFilter("agent-1")
        passing_evt = make_event(EventType.TOOL_CALLED, "agent-1")
        failing_evt = make_event(EventType.TOOL_CALLED, "agent-2")
        assert f.matches(passing_evt) is True
        assert f.matches(failing_evt) is False

    def test_or_compound_filter_matches_correctly(self) -> None:
        f = TypeFilter(EventType.AGENT_STARTED) | AgentFilter("agent-9")
        assert f.matches(make_event(EventType.AGENT_STARTED, "agent-2")) is True
        assert f.matches(make_event(EventType.CUSTOM, "agent-9")) is True
        assert f.matches(make_event(EventType.CUSTOM, "agent-1")) is False
