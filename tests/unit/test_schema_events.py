"""Unit tests for agentcore.schema.events.

Tests cover EventType enum, AgentEvent base class, ToolCallEvent,
DecisionEvent, and serialisation round-trips for each.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from agentcore.schema.events import (
    AgentEvent,
    DecisionEvent,
    EventType,
    ToolCallEvent,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_event() -> AgentEvent:
    return AgentEvent(event_type=EventType.AGENT_STARTED, agent_id="agent-001")


@pytest.fixture()
def tool_event() -> ToolCallEvent:
    return ToolCallEvent(
        event_type=EventType.TOOL_CALLED,
        agent_id="agent-002",
        tool_name="web_search",
        tool_input={"query": "agentcore sdk"},
        tool_output={"results": ["r1", "r2"]},
    )


@pytest.fixture()
def decision_event() -> DecisionEvent:
    return DecisionEvent(
        event_type=EventType.DECISION_MADE,
        agent_id="agent-003",
        decision="use_tool",
        reasoning="Query requires live data",
        confidence=0.92,
    )


# ---------------------------------------------------------------------------
# EventType enum
# ---------------------------------------------------------------------------


class TestEventType:
    def test_all_values_are_strings(self) -> None:
        for member in EventType:
            assert isinstance(member.value, str)

    def test_expected_members_present(self) -> None:
        expected = {
            "agent_started",
            "agent_stopped",
            "tool_called",
            "tool_completed",
            "tool_failed",
            "decision_made",
            "message_received",
            "message_sent",
            "error_occurred",
            "cost_incurred",
            "custom",
        }
        assert {m.value for m in EventType} == expected

    def test_str_mixin_allows_direct_comparison(self) -> None:
        assert EventType.AGENT_STARTED == "agent_started"


# ---------------------------------------------------------------------------
# AgentEvent construction
# ---------------------------------------------------------------------------


class TestAgentEventConstruction:
    def test_required_fields_stored(self, base_event: AgentEvent) -> None:
        assert base_event.event_type is EventType.AGENT_STARTED
        assert base_event.agent_id == "agent-001"

    def test_event_id_auto_generated_as_uuid4(self, base_event: AgentEvent) -> None:
        parsed = uuid.UUID(base_event.event_id, version=4)
        assert str(parsed) == base_event.event_id

    def test_two_events_get_different_event_ids(self) -> None:
        a = AgentEvent(EventType.CUSTOM, "agent-x")
        b = AgentEvent(EventType.CUSTOM, "agent-x")
        assert a.event_id != b.event_id

    def test_timestamp_defaults_to_utc_now(self, base_event: AgentEvent) -> None:
        assert isinstance(base_event.timestamp, datetime)
        assert base_event.timestamp.tzinfo is not None

    def test_data_defaults_to_empty_dict(self, base_event: AgentEvent) -> None:
        assert base_event.data == {}

    def test_metadata_defaults_to_empty_dict(self, base_event: AgentEvent) -> None:
        assert base_event.metadata == {}

    def test_parent_event_id_defaults_to_none(self, base_event: AgentEvent) -> None:
        assert base_event.parent_event_id is None

    def test_explicit_parent_event_id_stored(self) -> None:
        parent_id = str(uuid.uuid4())
        evt = AgentEvent(
            EventType.TOOL_COMPLETED,
            "agent-x",
            parent_event_id=parent_id,
        )
        assert evt.parent_event_id == parent_id


# ---------------------------------------------------------------------------
# AgentEvent serialisation
# ---------------------------------------------------------------------------


class TestAgentEventSerialisation:
    def test_to_dict_has_all_expected_keys(self, base_event: AgentEvent) -> None:
        d = base_event.to_dict()
        assert set(d.keys()) == {
            "event_id",
            "event_type",
            "agent_id",
            "timestamp",
            "data",
            "metadata",
            "parent_event_id",
        }

    def test_to_dict_event_type_is_string_value(self, base_event: AgentEvent) -> None:
        d = base_event.to_dict()
        assert d["event_type"] == "agent_started"

    def test_to_dict_timestamp_is_iso8601_string(self, base_event: AgentEvent) -> None:
        d = base_event.to_dict()
        ts = d["timestamp"]
        assert isinstance(ts, str)
        datetime.fromisoformat(ts)

    def test_round_trip_base_event(self, base_event: AgentEvent) -> None:
        restored = AgentEvent.from_dict(base_event.to_dict())
        assert restored.event_id == base_event.event_id
        assert restored.event_type is base_event.event_type
        assert restored.agent_id == base_event.agent_id

    def test_from_dict_invalid_event_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            AgentEvent.from_dict(
                {
                    "event_type": "totally_unknown",
                    "agent_id": "a1",
                }
            )

    def test_from_dict_missing_agent_id_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            AgentEvent.from_dict({"event_type": "agent_started"})

    def test_from_dict_generates_event_id_when_absent(self) -> None:
        payload: dict[str, object] = {
            "event_type": "agent_started",
            "agent_id": "a99",
        }
        evt = AgentEvent.from_dict(payload)
        assert isinstance(evt.event_id, str)
        uuid.UUID(evt.event_id, version=4)

    def test_from_dict_accepts_iso_timestamp_string(self) -> None:
        ts_str = "2025-06-01T12:00:00+00:00"
        payload: dict[str, object] = {
            "event_type": "agent_started",
            "agent_id": "a1",
            "timestamp": ts_str,
        }
        evt = AgentEvent.from_dict(payload)
        assert evt.timestamp == datetime.fromisoformat(ts_str)

    def test_from_dict_accepts_datetime_object_for_timestamp(self) -> None:
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        payload: dict[str, object] = {
            "event_type": "custom",
            "agent_id": "a2",
            "timestamp": ts,
        }
        evt = AgentEvent.from_dict(payload)
        assert evt.timestamp == ts


# ---------------------------------------------------------------------------
# ToolCallEvent
# ---------------------------------------------------------------------------


class TestToolCallEvent:
    def test_tool_name_stored(self, tool_event: ToolCallEvent) -> None:
        assert tool_event.tool_name == "web_search"

    def test_tool_input_stored(self, tool_event: ToolCallEvent) -> None:
        assert tool_event.tool_input == {"query": "agentcore sdk"}

    def test_tool_output_stored(self, tool_event: ToolCallEvent) -> None:
        assert tool_event.tool_output == {"results": ["r1", "r2"]}

    def test_tool_output_defaults_to_none(self) -> None:
        evt = ToolCallEvent(
            event_type=EventType.TOOL_CALLED,
            agent_id="a",
            tool_name="echo",
        )
        assert evt.tool_output is None

    def test_to_dict_includes_tool_fields(self, tool_event: ToolCallEvent) -> None:
        d = tool_event.to_dict()
        assert d["tool_name"] == "web_search"
        assert "tool_input" in d
        assert "tool_output" in d

    def test_round_trip_tool_event(self, tool_event: ToolCallEvent) -> None:
        restored = ToolCallEvent.from_dict(tool_event.to_dict())
        assert restored.tool_name == tool_event.tool_name
        assert restored.tool_input == tool_event.tool_input

    def test_from_dict_missing_tool_name_defaults_to_empty_string(self) -> None:
        payload: dict[str, object] = {
            "event_type": "tool_called",
            "agent_id": "a",
        }
        evt = ToolCallEvent.from_dict(payload)
        assert evt.tool_name == ""

    def test_is_agent_event_subclass(self, tool_event: ToolCallEvent) -> None:
        assert isinstance(tool_event, AgentEvent)


# ---------------------------------------------------------------------------
# DecisionEvent
# ---------------------------------------------------------------------------


class TestDecisionEvent:
    def test_decision_stored(self, decision_event: DecisionEvent) -> None:
        assert decision_event.decision == "use_tool"

    def test_reasoning_stored(self, decision_event: DecisionEvent) -> None:
        assert decision_event.reasoning == "Query requires live data"

    def test_confidence_stored(self, decision_event: DecisionEvent) -> None:
        assert decision_event.confidence == pytest.approx(0.92)

    def test_confidence_defaults_to_none(self) -> None:
        evt = DecisionEvent(
            event_type=EventType.DECISION_MADE,
            agent_id="a",
            decision="do_nothing",
        )
        assert evt.confidence is None

    def test_to_dict_includes_decision_fields(
        self, decision_event: DecisionEvent
    ) -> None:
        d = decision_event.to_dict()
        assert d["decision"] == "use_tool"
        assert d["reasoning"] == "Query requires live data"
        assert d["confidence"] == pytest.approx(0.92)

    def test_round_trip_decision_event(self, decision_event: DecisionEvent) -> None:
        restored = DecisionEvent.from_dict(decision_event.to_dict())
        assert restored.decision == decision_event.decision
        assert restored.reasoning == decision_event.reasoning
        assert restored.confidence == pytest.approx(decision_event.confidence)

    def test_from_dict_none_confidence_stays_none(self) -> None:
        payload: dict[str, object] = {
            "event_type": "decision_made",
            "agent_id": "a",
            "decision": "skip",
            "confidence": None,
        }
        evt = DecisionEvent.from_dict(payload)
        assert evt.confidence is None

    def test_is_agent_event_subclass(self, decision_event: DecisionEvent) -> None:
        assert isinstance(decision_event, AgentEvent)
