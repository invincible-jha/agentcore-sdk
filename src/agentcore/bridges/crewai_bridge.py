"""CrewAI task event bridge.

Maps CrewAI task lifecycle events into agentcore :class:`AgentEvent` objects.

CrewAI represents task events as dicts with an ``"event_type"`` key that
mirrors CrewAI's internal task state machine.

Supported event types
---------------------
- ``"task_started"``     → AGENT_STARTED
- ``"task_completed"``   → AGENT_STOPPED
- ``"task_failed"``      → ERROR_OCCURRED
- ``"tool_use"``         → TOOL_CALLED
- ``"tool_result"``      → TOOL_COMPLETED
- ``"agent_message"``    → MESSAGE_SENT
- Any unrecognised type  → CUSTOM
"""
from __future__ import annotations

from typing import Any

from agentcore.bridges.base import FrameworkBridge
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType


_CREW_EVENT_MAP: dict[str, EventType] = {
    "task_started": EventType.AGENT_STARTED,
    "task_completed": EventType.AGENT_STOPPED,
    "task_failed": EventType.ERROR_OCCURRED,
    "tool_use": EventType.TOOL_CALLED,
    "tool_result": EventType.TOOL_COMPLETED,
    "agent_message": EventType.MESSAGE_SENT,
}


class CrewAIBridge(FrameworkBridge):
    """Bridge that converts CrewAI task events into agentcore events.

    Example
    -------
    ::

        bus = EventBus()
        bridge = CrewAIBridge(agent_id="crew-agent-1", bus=bus)
        event = bridge.emit_event({
            "event_type": "task_started",
            "task_name": "research_task",
            "agent_role": "researcher",
        })
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)

    @property
    def supported_framework(self) -> str:
        """Return ``"crewai"``."""
        return "crewai"

    def adapt_event(self, framework_event: Any) -> AgentEvent | None:
        """Convert a CrewAI task event dict to an :class:`AgentEvent`.

        Parameters
        ----------
        framework_event:
            A dict with at least an ``"event_type"`` key.

        Returns
        -------
        AgentEvent | None
            The mapped event, or None if *framework_event* is not a dict.
        """
        if not isinstance(framework_event, dict):
            return None

        crew_event_type = framework_event.get("event_type", "unknown")
        event_type = _CREW_EVENT_MAP.get(crew_event_type, EventType.CUSTOM)

        data: dict[str, object] = {
            "crew_event_type": crew_event_type,
        }

        # Task-level context
        if "task_name" in framework_event:
            data["task_name"] = framework_event["task_name"]
        if "task_id" in framework_event:
            data["task_id"] = framework_event["task_id"]
        if "agent_role" in framework_event:
            data["agent_role"] = framework_event["agent_role"]

        # Tool events
        if "tool_name" in framework_event:
            data["tool_name"] = framework_event["tool_name"]
        if "tool_input" in framework_event:
            data["tool_input"] = framework_event["tool_input"]
        if "tool_output" in framework_event:
            data["tool_output"] = framework_event["tool_output"]

        # Error events
        if "error" in framework_event:
            data["error"] = str(framework_event["error"])

        # Message events
        if "message" in framework_event:
            data["message"] = framework_event["message"]
        if "recipient" in framework_event:
            data["recipient"] = framework_event["recipient"]

        # Output / result
        if "output" in framework_event:
            data["output"] = framework_event["output"]

        return AgentEvent(
            event_type=event_type,
            agent_id=self._agent_id,
            data=data,
            metadata={"source_framework": "crewai", "crew_event_type": crew_event_type},
        )


__all__ = ["CrewAIBridge"]
