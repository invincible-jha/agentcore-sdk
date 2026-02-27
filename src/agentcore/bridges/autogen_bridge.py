"""AutoGen message bridge.

Maps AutoGen conversational messages into agentcore :class:`AgentEvent` objects.

AutoGen uses a message dict structure with ``"role"`` and ``"content"`` fields
(similar to OpenAI chat messages) plus optional metadata like ``"name"`` and
``"function_call"``.

Supported message roles
-----------------------
- ``"user"``       → MESSAGE_RECEIVED
- ``"assistant"``  → MESSAGE_SENT
- ``"function"``   → TOOL_COMPLETED
- ``"system"``     → AGENT_STARTED (system prompt injection)
- Any other role   → CUSTOM
"""
from __future__ import annotations

from typing import Any

from agentcore.bridges.base import FrameworkBridge
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType


_ROLE_EVENT_MAP: dict[str, EventType] = {
    "user": EventType.MESSAGE_RECEIVED,
    "assistant": EventType.MESSAGE_SENT,
    "function": EventType.TOOL_COMPLETED,
    "system": EventType.AGENT_STARTED,
}


class AutoGenBridge(FrameworkBridge):
    """Bridge that converts AutoGen messages into agentcore events.

    AutoGen uses a message-passing paradigm.  Each message contains a role,
    content, and optional function call information.

    Example
    -------
    ::

        bus = EventBus()
        bridge = AutoGenBridge(agent_id="autogen-agent-1", bus=bus)
        event = bridge.emit_event({
            "role": "assistant",
            "content": "I will search for that information.",
            "name": "AssistantAgent",
        })
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)

    @property
    def supported_framework(self) -> str:
        """Return ``"autogen"``."""
        return "autogen"

    def adapt_event(self, framework_event: Any) -> AgentEvent | None:
        """Convert an AutoGen message dict to an :class:`AgentEvent`.

        Parameters
        ----------
        framework_event:
            A dict with at least a ``"role"`` key.

        Returns
        -------
        AgentEvent | None
            The mapped event, or None if *framework_event* is not a dict.
        """
        if not isinstance(framework_event, dict):
            return None

        role = framework_event.get("role", "unknown")
        event_type = _ROLE_EVENT_MAP.get(role, EventType.CUSTOM)

        data: dict[str, object] = {
            "role": role,
        }

        # Message content
        if "content" in framework_event:
            data["content"] = framework_event["content"]

        # Agent name
        if "name" in framework_event:
            data["agent_name"] = framework_event["name"]

        # Function / tool call (OpenAI-style)
        if "function_call" in framework_event:
            fc = framework_event["function_call"]
            data["function_call"] = fc
            if isinstance(fc, dict):
                data["tool_name"] = fc.get("name", "")
                data["tool_input"] = fc.get("arguments", {})
            # Override event type for function calls from assistant
            if role == "assistant":
                event_type = EventType.TOOL_CALLED

        # Function result
        if role == "function":
            if "content" in framework_event:
                data["tool_output"] = framework_event["content"]
            if "name" in framework_event:
                data["tool_name"] = framework_event["name"]

        # Conversation context
        if "conversation_id" in framework_event:
            data["conversation_id"] = framework_event["conversation_id"]

        # AutoGen termination signal
        if framework_event.get("content") == "TERMINATE":
            event_type = EventType.AGENT_STOPPED
            data["reason"] = "termination_signal"

        return AgentEvent(
            event_type=event_type,
            agent_id=self._agent_id,
            data=data,
            metadata={"source_framework": "autogen", "message_role": role},
        )


__all__ = ["AutoGenBridge"]
