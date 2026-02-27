"""Tests for agentcore.bridges.crewai_bridge."""
from __future__ import annotations

import pytest

from agentcore.bridges.crewai_bridge import CrewAIBridge
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus() -> EventBus:
    return EventBus()


@pytest.fixture()
def bridge(bus: EventBus) -> CrewAIBridge:
    return CrewAIBridge(agent_id="crew-agent-1", bus=bus)


# ---------------------------------------------------------------------------
# Basic attributes
# ---------------------------------------------------------------------------


class TestCrewAIBridgeAttributes:
    def test_supported_framework(self, bridge: CrewAIBridge) -> None:
        assert bridge.supported_framework == "crewai"

    def test_agent_id(self, bridge: CrewAIBridge) -> None:
        assert bridge.agent_id == "crew-agent-1"

    def test_repr_contains_framework(self, bridge: CrewAIBridge) -> None:
        assert "crewai" in repr(bridge)


# ---------------------------------------------------------------------------
# Non-dict input
# ---------------------------------------------------------------------------


class TestAdaptNonDict:
    def test_none_returns_none(self, bridge: CrewAIBridge) -> None:
        assert bridge.adapt_event(None) is None

    def test_int_returns_none(self, bridge: CrewAIBridge) -> None:
        assert bridge.adapt_event(42) is None


# ---------------------------------------------------------------------------
# Event type mapping
# ---------------------------------------------------------------------------


class TestEventTypeMapping:
    @pytest.mark.parametrize(
        "crew_event_type,expected_event_type",
        [
            ("task_started", EventType.AGENT_STARTED),
            ("task_completed", EventType.AGENT_STOPPED),
            ("task_failed", EventType.ERROR_OCCURRED),
            ("tool_use", EventType.TOOL_CALLED),
            ("tool_result", EventType.TOOL_COMPLETED),
            ("agent_message", EventType.MESSAGE_SENT),
        ],
    )
    def test_known_crew_event_types(
        self,
        bridge: CrewAIBridge,
        crew_event_type: str,
        expected_event_type: EventType,
    ) -> None:
        event = bridge.adapt_event({"event_type": crew_event_type})
        assert event is not None
        assert event.event_type == expected_event_type

    def test_unknown_event_type_maps_to_custom(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event({"event_type": "new_crew_event"})
        assert event is not None
        assert event.event_type == EventType.CUSTOM

    def test_empty_dict_uses_custom(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event({})
        assert event is not None
        assert event.event_type == EventType.CUSTOM


# ---------------------------------------------------------------------------
# Data enrichment
# ---------------------------------------------------------------------------


class TestDataEnrichment:
    def test_task_name_in_data(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event(
            {"event_type": "task_started", "task_name": "research_task"}
        )
        assert event is not None
        assert event.data["task_name"] == "research_task"

    def test_agent_role_in_data(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event(
            {"event_type": "task_started", "agent_role": "researcher"}
        )
        assert event is not None
        assert event.data["agent_role"] == "researcher"

    def test_tool_name_and_input_in_data(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event(
            {
                "event_type": "tool_use",
                "tool_name": "search_tool",
                "tool_input": {"query": "AI 2026"},
            }
        )
        assert event is not None
        assert event.data["tool_name"] == "search_tool"
        assert event.data["tool_input"] == {"query": "AI 2026"}

    def test_error_in_data(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event(
            {"event_type": "task_failed", "error": "timeout exceeded"}
        )
        assert event is not None
        assert "timeout exceeded" in str(event.data["error"])

    def test_output_in_data(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event(
            {"event_type": "task_completed", "output": "Task result here"}
        )
        assert event is not None
        assert event.data["output"] == "Task result here"

    def test_message_in_data(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event(
            {"event_type": "agent_message", "message": "Hello team", "recipient": "crew-2"}
        )
        assert event is not None
        assert event.data["message"] == "Hello team"
        assert event.data["recipient"] == "crew-2"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_source_framework_in_metadata(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event({"event_type": "task_started"})
        assert event is not None
        assert event.metadata["source_framework"] == "crewai"

    def test_crew_event_type_in_metadata(self, bridge: CrewAIBridge) -> None:
        event = bridge.adapt_event({"event_type": "tool_use"})
        assert event is not None
        assert event.metadata["crew_event_type"] == "tool_use"


# ---------------------------------------------------------------------------
# Emit / batch
# ---------------------------------------------------------------------------


class TestEmit:
    def test_emit_event_returns_agent_event(self, bridge: CrewAIBridge) -> None:
        event = bridge.emit_event({"event_type": "task_started"})
        assert isinstance(event, AgentEvent)

    def test_emit_batch_correct_count(self, bridge: CrewAIBridge) -> None:
        raw_events = [
            {"event_type": "task_started"},
            {"event_type": "tool_use"},
            {"event_type": "task_completed"},
        ]
        events = bridge.emit_batch(raw_events)
        assert len(events) == 3
