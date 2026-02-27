"""Microsoft Agents SDK adapter for agentcore-sdk.

Emits ``AgentEvent`` objects by monkey-patching activity handler methods
and agent turn processing when the Microsoft Agents SDK is installed.
Degrades gracefully to a no-op stub when ``microsoft-agents`` is not installed.

Shipped in this module
----------------------
- MicrosoftAgentAdapter   — instruments a Microsoft Agents SDK agent with event emission

Extension points
----------------
Teams channel activity correlation, Adaptive Card event capture, and Bot Framework
Composer workflow event mapping can be implemented as plugins using the adapter extension API.
"""
from __future__ import annotations

import logging
from typing import Any

from agentcore.adapters.base import FrameworkAdapter
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType, ToolCallEvent

logger = logging.getLogger(__name__)

# Optional Microsoft Agents SDK import
try:
    import microsoft.agents  # type: ignore[import-not-found]

    _MICROSOFT_AGENTS_AVAILABLE = True
except ImportError:
    _MICROSOFT_AGENTS_AVAILABLE = False
    microsoft = None  # type: ignore[assignment]


class MicrosoftAgentAdapter(FrameworkAdapter):
    """Instruments a Microsoft Agents SDK agent with ``AgentEvent`` emission.

    When ``microsoft-agents`` is installed, :meth:`wrap` patches the agent's
    ``on_message_activity`` and ``on_turn`` methods (or equivalent) to emit
    ``AGENT_STARTED``, ``MESSAGE_RECEIVED``, ``AGENT_STOPPED``, and
    ``ERROR_OCCURRED`` events.

    When the SDK is absent, :meth:`wrap` returns the original object
    unchanged with a warning log.

    Parameters
    ----------
    agent_id:
        ID to associate with emitted events.
    bus:
        Event bus to emit on.

    Examples
    --------
    ::

        from agentcore.adapters.microsoft_agents import MicrosoftAgentAdapter
        from agentcore.bus import EventBus

        bus = EventBus()
        adapter = MicrosoftAgentAdapter("my-ms-agent", bus)
        instrumented_bot = adapter.wrap(my_activity_handler)
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)
        self._original_on_turn: Any = None
        self._original_on_message_activity: Any = None

    def get_framework_name(self) -> str:
        return "microsoft_agents"

    def wrap(self, agent_or_callable: Any) -> Any:  # noqa: ANN401
        """Patch activity handler methods on *agent_or_callable*.

        Parameters
        ----------
        agent_or_callable:
            A Microsoft Agents SDK ``ActivityHandler`` or compatible bot object.

        Returns
        -------
        Any
            The same object with patched activity handler methods, or unchanged
            if the SDK is not installed.
        """
        if not _MICROSOFT_AGENTS_AVAILABLE:
            logger.warning(
                "microsoft-agents is not installed; MicrosoftAgentAdapter is a no-op. "
                "Install microsoft-agents to enable Microsoft Agents SDK event integration."
            )
            return agent_or_callable

        agent = agent_or_callable
        adapter_ref = self

        # Patch on_turn — the outermost entry point for all Bot Framework activity
        if hasattr(agent, "on_turn"):
            original_on_turn = agent.on_turn

            async def patched_on_turn(turn_context: object) -> None:
                await adapter_ref._bus.emit(
                    AgentEvent(EventType.AGENT_STARTED, adapter_ref._agent_id)
                )
                try:
                    await original_on_turn(turn_context)
                    await adapter_ref._bus.emit(
                        AgentEvent(
                            EventType.AGENT_STOPPED,
                            adapter_ref._agent_id,
                            data={"success": True},
                        )
                    )
                except Exception as exc:
                    await adapter_ref._bus.emit(
                        AgentEvent(
                            EventType.ERROR_OCCURRED,
                            adapter_ref._agent_id,
                            data={
                                "error": str(exc),
                                "error_type": type(exc).__name__,
                            },
                        )
                    )
                    raise

            agent.on_turn = patched_on_turn  # type: ignore[method-assign]

        # Patch on_message_activity — standard entry point for text messages
        if hasattr(agent, "on_message_activity"):
            original_on_message_activity = agent.on_message_activity

            async def patched_on_message_activity(
                turn_context: object,
            ) -> None:
                activity_text: str = ""
                if hasattr(turn_context, "activity"):
                    activity = turn_context.activity  # type: ignore[union-attr]
                    activity_text = getattr(activity, "text", "") or ""
                await adapter_ref._bus.emit(
                    AgentEvent(
                        EventType.MESSAGE_RECEIVED,
                        adapter_ref._agent_id,
                        data={"text": activity_text},
                    )
                )
                await original_on_message_activity(turn_context)

            agent.on_message_activity = (  # type: ignore[method-assign]
                patched_on_message_activity
            )

        # Patch invoke_activity if present (skill / adaptive card actions)
        if hasattr(agent, "on_invoke_activity"):
            original_on_invoke = agent.on_invoke_activity

            async def patched_on_invoke_activity(turn_context: object) -> Any:  # noqa: ANN401
                activity = getattr(turn_context, "activity", None)
                invoke_name = ""
                if activity is not None:
                    invoke_name = getattr(activity, "name", "") or ""
                await adapter_ref._bus.emit(
                    ToolCallEvent(
                        event_type=EventType.TOOL_CALLED,
                        agent_id=adapter_ref._agent_id,
                        tool_name=invoke_name or "invoke_activity",
                        tool_input={},
                    )
                )
                try:
                    result = await original_on_invoke(turn_context)
                    await adapter_ref._bus.emit(
                        ToolCallEvent(
                            event_type=EventType.TOOL_COMPLETED,
                            agent_id=adapter_ref._agent_id,
                            tool_name=invoke_name or "invoke_activity",
                            tool_output=str(result) if result is not None else "",
                        )
                    )
                    return result
                except Exception as exc:
                    await adapter_ref._bus.emit(
                        ToolCallEvent(
                            event_type=EventType.TOOL_FAILED,
                            agent_id=adapter_ref._agent_id,
                            tool_name=invoke_name or "invoke_activity",
                            tool_output=str(exc),
                            data={
                                "error": str(exc),
                                "error_type": type(exc).__name__,
                            },
                        )
                    )
                    raise

            agent.on_invoke_activity = (  # type: ignore[method-assign]
                patched_on_invoke_activity
            )

        return agent

    def emit_events(self, bus: EventBus) -> None:
        """Update the event bus used by this adapter."""
        self._bus = bus
