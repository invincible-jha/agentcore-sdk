"""Tests for agentcore.bridges.autogen_bridge."""
from __future__ import annotations

import pytest

from agentcore.bridges.autogen_bridge import AutoGenBridge
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus() -> EventBus:
    return EventBus()


@pytest.fixture()
def bridge(bus: EventBus) -> AutoGenBridge:
    return AutoGenBridge(agent_id="autogen-agent-1", bus=bus)


# ---------------------------------------------------------------------------
# Basic attributes
# ---------------------------------------------------------------------------


class TestAutoGenBridgeAttributes:
    def test_supported_framework(self, bridge: AutoGenBridge) -> None:
        assert bridge.supported_framework == "autogen"

    def test_agent_id(self, bridge: AutoGenBridge) -> None:
        assert bridge.agent_id == "autogen-agent-1"

    def test_repr_contains_framework(self, bridge: AutoGenBridge) -> None:
        assert "autogen" in repr(bridge)


# ---------------------------------------------------------------------------
# Non-dict input
# ---------------------------------------------------------------------------


class TestAdaptNonDict:
    def test_none_returns_none(self, bridge: AutoGenBridge) -> None:
        assert bridge.adapt_event(None) is None

    def test_string_returns_none(self, bridge: AutoGenBridge) -> None:
        assert bridge.adapt_event("hello") is None


# ---------------------------------------------------------------------------
# Role mapping
# ---------------------------------------------------------------------------


class TestRoleMapping:
    @pytest.mark.parametrize(
        "role,expected_event_type",
        [
            ("user", EventType.MESSAGE_RECEIVED),
            ("assistant", EventType.MESSAGE_SENT),
            ("function", EventType.TOOL_COMPLETED),
            ("system", EventType.AGENT_STARTED),
        ],
    )
    def test_known_roles(
        self,
        bridge: AutoGenBridge,
        role: str,
        expected_event_type: EventType,
    ) -> None:
        event = bridge.adapt_event({"role": role, "content": "test"})
        assert event is not None
        # Function calls from assistant override to TOOL_CALLED
        if role != "assistant":
            assert event.event_type == expected_event_type

    def test_unknown_role_maps_to_custom(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"role": "observer", "content": "..."})
        assert event is not None
        assert event.event_type == EventType.CUSTOM

    def test_missing_role_maps_to_custom(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"content": "no role"})
        assert event is not None
        assert event.event_type == EventType.CUSTOM


# ---------------------------------------------------------------------------
# Data enrichment
# ---------------------------------------------------------------------------


class TestDataEnrichment:
    def test_content_in_data(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"role": "user", "content": "Hello!"})
        assert event is not None
        assert event.data["content"] == "Hello!"

    def test_agent_name_in_data(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"role": "assistant", "name": "AssistantAgent", "content": "Hi"})
        assert event is not None
        assert event.data["agent_name"] == "AssistantAgent"

    def test_function_call_in_data(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event(
            {
                "role": "assistant",
                "function_call": {"name": "search", "arguments": {"q": "AI"}},
                "content": "",
            }
        )
        assert event is not None
        assert event.data["tool_name"] == "search"
        assert event.event_type == EventType.TOOL_CALLED

    def test_function_role_sets_tool_output(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event(
            {"role": "function", "name": "search", "content": "result here"}
        )
        assert event is not None
        assert event.data["tool_output"] == "result here"
        assert event.data["tool_name"] == "search"

    def test_conversation_id_in_data(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event(
            {"role": "user", "content": "hi", "conversation_id": "conv-42"}
        )
        assert event is not None
        assert event.data["conversation_id"] == "conv-42"


# ---------------------------------------------------------------------------
# Termination signal
# ---------------------------------------------------------------------------


class TestTerminationSignal:
    def test_terminate_content_maps_to_stopped(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"role": "assistant", "content": "TERMINATE"})
        assert event is not None
        assert event.event_type == EventType.AGENT_STOPPED

    def test_terminate_data_has_reason(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"role": "assistant", "content": "TERMINATE"})
        assert event is not None
        assert event.data.get("reason") == "termination_signal"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_source_framework_in_metadata(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"role": "user", "content": "hi"})
        assert event is not None
        assert event.metadata["source_framework"] == "autogen"

    def test_message_role_in_metadata(self, bridge: AutoGenBridge) -> None:
        event = bridge.adapt_event({"role": "user", "content": "hi"})
        assert event is not None
        assert event.metadata["message_role"] == "user"


# ---------------------------------------------------------------------------
# Emit / batch
# ---------------------------------------------------------------------------


class TestEmit:
    def test_emit_event_returns_agent_event(self, bridge: AutoGenBridge) -> None:
        event = bridge.emit_event({"role": "user", "content": "start"})
        assert isinstance(event, AgentEvent)

    def test_emit_batch_skips_non_dict(self, bridge: AutoGenBridge) -> None:
        events_raw = [
            {"role": "user", "content": "hello"},
            42,  # should be skipped
            {"role": "assistant", "content": "hi"},
        ]
        events = bridge.emit_batch(events_raw)
        assert len(events) == 2
