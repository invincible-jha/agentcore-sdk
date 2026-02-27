"""Tests for agentcore.bridges.langchain_bridge."""
from __future__ import annotations

import pytest

from agentcore.bridges.langchain_bridge import LangChainBridge
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus() -> EventBus:
    return EventBus()


@pytest.fixture()
def bridge(bus: EventBus) -> LangChainBridge:
    return LangChainBridge(agent_id="lc-agent-1", bus=bus)


# ---------------------------------------------------------------------------
# Basic attributes
# ---------------------------------------------------------------------------


class TestLangChainBridgeAttributes:
    def test_supported_framework(self, bridge: LangChainBridge) -> None:
        assert bridge.supported_framework == "langchain"

    def test_agent_id(self, bridge: LangChainBridge) -> None:
        assert bridge.agent_id == "lc-agent-1"

    def test_repr_contains_framework(self, bridge: LangChainBridge) -> None:
        assert "langchain" in repr(bridge)


# ---------------------------------------------------------------------------
# adapt_event — non-dict input
# ---------------------------------------------------------------------------


class TestAdaptNonDict:
    def test_none_returns_none(self, bridge: LangChainBridge) -> None:
        assert bridge.adapt_event(None) is None

    def test_string_returns_none(self, bridge: LangChainBridge) -> None:
        assert bridge.adapt_event("not a dict") is None

    def test_list_returns_none(self, bridge: LangChainBridge) -> None:
        assert bridge.adapt_event([1, 2, 3]) is None


# ---------------------------------------------------------------------------
# Callback type mapping
# ---------------------------------------------------------------------------


class TestCallbackTypeMapping:
    @pytest.mark.parametrize(
        "callback_type,expected_event_type",
        [
            ("on_llm_start", EventType.AGENT_STARTED),
            ("on_llm_end", EventType.AGENT_STOPPED),
            ("on_tool_start", EventType.TOOL_CALLED),
            ("on_tool_end", EventType.TOOL_COMPLETED),
            ("on_tool_error", EventType.TOOL_FAILED),
            ("on_chain_start", EventType.AGENT_STARTED),
            ("on_chain_end", EventType.AGENT_STOPPED),
            ("on_agent_action", EventType.DECISION_MADE),
        ],
    )
    def test_known_callback_types(
        self,
        bridge: LangChainBridge,
        callback_type: str,
        expected_event_type: EventType,
    ) -> None:
        event = bridge.adapt_event({"callback_type": callback_type})
        assert event is not None
        assert event.event_type == expected_event_type

    def test_unknown_callback_type_maps_to_custom(
        self, bridge: LangChainBridge
    ) -> None:
        event = bridge.adapt_event({"callback_type": "on_something_new"})
        assert event is not None
        assert event.event_type == EventType.CUSTOM

    def test_missing_callback_type_maps_to_custom(
        self, bridge: LangChainBridge
    ) -> None:
        event = bridge.adapt_event({})
        assert event is not None
        assert event.event_type == EventType.CUSTOM


# ---------------------------------------------------------------------------
# Data enrichment
# ---------------------------------------------------------------------------


class TestDataEnrichment:
    def test_tool_name_in_data(self, bridge: LangChainBridge) -> None:
        event = bridge.adapt_event(
            {"callback_type": "on_tool_start", "tool": "calculator"}
        )
        assert event is not None
        assert event.data["tool_name"] == "calculator"

    def test_tool_input_in_data(self, bridge: LangChainBridge) -> None:
        event = bridge.adapt_event(
            {"callback_type": "on_tool_start", "tool": "search", "tool_input": {"q": "test"}}
        )
        assert event is not None
        assert event.data["tool_input"] == {"q": "test"}

    def test_error_in_data(self, bridge: LangChainBridge) -> None:
        event = bridge.adapt_event(
            {"callback_type": "on_tool_error", "error": "connection refused"}
        )
        assert event is not None
        assert "connection refused" in str(event.data["error"])

    def test_action_in_data(self, bridge: LangChainBridge) -> None:
        event = bridge.adapt_event(
            {"callback_type": "on_agent_action", "action": "search", "action_input": "query"}
        )
        assert event is not None
        assert event.data["action"] == "search"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_source_framework_in_metadata(self, bridge: LangChainBridge) -> None:
        event = bridge.adapt_event({"callback_type": "on_llm_start"})
        assert event is not None
        assert event.metadata["source_framework"] == "langchain"

    def test_callback_type_in_metadata(self, bridge: LangChainBridge) -> None:
        event = bridge.adapt_event({"callback_type": "on_tool_end"})
        assert event is not None
        assert event.metadata["callback_type"] == "on_tool_end"


# ---------------------------------------------------------------------------
# emit_event publishes to bus
# ---------------------------------------------------------------------------


class TestEmitEvent:
    def test_emit_event_returns_event(self, bridge: LangChainBridge) -> None:
        event = bridge.emit_event({"callback_type": "on_llm_start"})
        assert isinstance(event, AgentEvent)

    def test_emit_batch_returns_list(self, bridge: LangChainBridge) -> None:
        events_raw = [
            {"callback_type": "on_tool_start", "tool": "calc"},
            {"callback_type": "on_tool_end"},
        ]
        events = bridge.emit_batch(events_raw)
        assert len(events) == 2

    def test_emit_batch_skips_none(self, bridge: LangChainBridge) -> None:
        events_raw = [
            {"callback_type": "on_llm_start"},
            "not-a-dict",  # should be skipped
            {"callback_type": "on_llm_end"},
        ]
        events = bridge.emit_batch(events_raw)
        assert len(events) == 2
