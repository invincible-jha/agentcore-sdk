"""Tests for AEP version field in AgentEvent."""
import pytest
from agentcore.schema.events import AgentEvent, EventType, ToolCallEvent, DecisionEvent


class TestAEPVersion:
    """Verify AEP version field is present and correct."""

    def test_default_aep_version(self) -> None:
        event = AgentEvent(event_type=EventType.AGENT_STARTED, agent_id="agent-1")
        assert event.aep_version == "1.0.0"

    def test_custom_aep_version(self) -> None:
        event = AgentEvent(
            event_type=EventType.AGENT_STARTED,
            agent_id="agent-1",
            aep_version="2.0.0",
        )
        assert event.aep_version == "2.0.0"

    def test_aep_version_in_to_dict(self) -> None:
        event = AgentEvent(event_type=EventType.AGENT_STARTED, agent_id="agent-1")
        d = event.to_dict()
        assert "aep_version" in d
        assert d["aep_version"] == "1.0.0"

    def test_aep_version_from_dict(self) -> None:
        payload = {
            "event_type": "agent_started",
            "agent_id": "agent-1",
            "aep_version": "1.0.0",
        }
        event = AgentEvent.from_dict(payload)
        assert event.aep_version == "1.0.0"

    def test_aep_version_from_dict_default(self) -> None:
        """If aep_version is missing from dict, default to 1.0.0."""
        payload = {
            "event_type": "agent_started",
            "agent_id": "agent-1",
        }
        event = AgentEvent.from_dict(payload)
        assert event.aep_version == "1.0.0"

    def test_tool_call_event_has_aep_version(self) -> None:
        event = ToolCallEvent(
            event_type=EventType.TOOL_CALLED,
            agent_id="agent-1",
            tool_name="search",
        )
        assert event.aep_version == "1.0.0"
        assert event.to_dict()["aep_version"] == "1.0.0"

    def test_decision_event_has_aep_version(self) -> None:
        event = DecisionEvent(
            event_type=EventType.DECISION_MADE,
            agent_id="agent-1",
            decision="use_tool",
        )
        assert event.aep_version == "1.0.0"
        assert event.to_dict()["aep_version"] == "1.0.0"

    def test_round_trip_preserves_aep_version(self) -> None:
        original = AgentEvent(
            event_type=EventType.AGENT_STARTED,
            agent_id="agent-1",
            aep_version="1.0.0",
        )
        d = original.to_dict()
        restored = AgentEvent.from_dict(d)
        assert restored.aep_version == original.aep_version
