"""LangChain callback bridge.

Maps LangChain callback payloads into agentcore :class:`AgentEvent` objects.

LangChain callbacks use a dict-based payload convention.  This bridge
expects dicts with a ``"callback_type"`` key and maps them to standard
:class:`~agentcore.schema.events.EventType` values.

Supported callback types
------------------------
- ``"on_llm_start"``        → AGENT_STARTED
- ``"on_llm_end"``          → AGENT_STOPPED
- ``"on_tool_start"``       → TOOL_CALLED
- ``"on_tool_end"``         → TOOL_COMPLETED
- ``"on_tool_error"``       → TOOL_FAILED
- ``"on_chain_start"``      → AGENT_STARTED
- ``"on_chain_end"``        → AGENT_STOPPED
- ``"on_agent_action"``     → DECISION_MADE
- Any unrecognised type     → CUSTOM
"""
from __future__ import annotations

from typing import Any

from agentcore.bridges.base import FrameworkBridge
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType


# Mapping of LangChain callback type → EventType
_CALLBACK_TYPE_MAP: dict[str, EventType] = {
    "on_llm_start": EventType.AGENT_STARTED,
    "on_llm_end": EventType.AGENT_STOPPED,
    "on_tool_start": EventType.TOOL_CALLED,
    "on_tool_end": EventType.TOOL_COMPLETED,
    "on_tool_error": EventType.TOOL_FAILED,
    "on_chain_start": EventType.AGENT_STARTED,
    "on_chain_end": EventType.AGENT_STOPPED,
    "on_agent_action": EventType.DECISION_MADE,
}


class LangChainBridge(FrameworkBridge):
    """Bridge that converts LangChain callbacks into agentcore events.

    Example
    -------
    ::

        bus = EventBus()
        bridge = LangChainBridge(agent_id="lc-agent-1", bus=bus)
        event = bridge.emit_event({
            "callback_type": "on_tool_start",
            "tool": "web_search",
            "tool_input": {"query": "AI news"},
        })
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)

    @property
    def supported_framework(self) -> str:
        """Return ``"langchain"``."""
        return "langchain"

    def adapt_event(self, framework_event: Any) -> AgentEvent | None:
        """Convert a LangChain callback dict to an :class:`AgentEvent`.

        Parameters
        ----------
        framework_event:
            A dict with at least a ``"callback_type"`` key.

        Returns
        -------
        AgentEvent | None
            The mapped event, or None if *framework_event* is not a dict.
        """
        if not isinstance(framework_event, dict):
            return None

        callback_type = framework_event.get("callback_type", "unknown")
        event_type = _CALLBACK_TYPE_MAP.get(callback_type, EventType.CUSTOM)

        data: dict[str, object] = {
            "callback_type": callback_type,
        }

        # Enrich data for tool events
        if "tool" in framework_event:
            data["tool_name"] = framework_event["tool"]
        if "tool_input" in framework_event:
            data["tool_input"] = framework_event["tool_input"]
        if "tool_output" in framework_event:
            data["tool_output"] = framework_event["tool_output"]
        if "error" in framework_event:
            data["error"] = str(framework_event["error"])

        # Enrich data for LLM events
        if "serialized" in framework_event:
            data["model_info"] = framework_event.get("serialized", {})

        # Enrich for agent action
        if "action" in framework_event:
            data["action"] = framework_event["action"]
            data["action_input"] = framework_event.get("action_input", "")

        return AgentEvent(
            event_type=event_type,
            agent_id=self._agent_id,
            data=data,
            metadata={"source_framework": "langchain", "callback_type": callback_type},
        )


__all__ = ["LangChainBridge"]
