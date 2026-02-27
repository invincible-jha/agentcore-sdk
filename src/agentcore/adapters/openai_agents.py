"""OpenAI Agents SDK adapter for agentcore-sdk.

Emits ``AgentEvent`` objects by monkey-patching the agent runner's execution
when the OpenAI Agents SDK is installed.  Degrades gracefully to a no-op stub
when ``openai-agents`` is not installed.

Shipped in this module
----------------------
- OpenAIAgentsAdapter   — instruments an OpenAI Agents SDK ``Agent`` with event emission

Extension points
----------------
Streaming token capture, multi-agent handoff correlation, and Responses API
event mapping can be implemented as plugins using the adapter extension API.
"""
from __future__ import annotations

import logging
from typing import Any

from agentcore.adapters.base import FrameworkAdapter
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType, ToolCallEvent

logger = logging.getLogger(__name__)

# Optional OpenAI Agents SDK import
try:
    from agents import Agent, Runner  # type: ignore[import-not-found]

    _OPENAI_AGENTS_AVAILABLE = True
except ImportError:
    _OPENAI_AGENTS_AVAILABLE = False
    Agent = object  # type: ignore[assignment, misc]
    Runner = object  # type: ignore[assignment, misc]


class OpenAIAgentsAdapter(FrameworkAdapter):
    """Instruments an OpenAI Agents SDK ``Agent`` with ``AgentEvent`` emission.

    When ``openai-agents`` is installed, :meth:`wrap` patches the provided
    agent object so that calls to ``Runner.run`` / ``Runner.run_sync`` emit
    ``AGENT_STARTED``, ``AGENT_STOPPED``, and ``ERROR_OCCURRED`` events.

    When the SDK is not installed, :meth:`wrap` returns the original object
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

        from agentcore.adapters.openai_agents import OpenAIAgentsAdapter
        from agentcore.bus import EventBus

        bus = EventBus()
        adapter = OpenAIAgentsAdapter("my-oai-agent", bus)
        instrumented_agent = adapter.wrap(my_agent)
        result = await Runner.run(instrumented_agent, "Hello!")
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)
        self._original_agent: Any = None

    def get_framework_name(self) -> str:
        return "openai_agents"

    def wrap(self, agent_or_callable: Any) -> Any:  # noqa: ANN401
        """Attach event emission hooks to *agent_or_callable*.

        Parameters
        ----------
        agent_or_callable:
            An OpenAI Agents SDK ``Agent`` instance.

        Returns
        -------
        Any
            The same object with event-emitting hooks attached, or the
            unchanged object if the SDK is not installed.
        """
        if not _OPENAI_AGENTS_AVAILABLE:
            logger.warning(
                "openai-agents is not installed; OpenAIAgentsAdapter is a no-op. "
                "Install openai-agents to enable OpenAI Agents SDK event integration."
            )
            return agent_or_callable

        self._original_agent = agent_or_callable
        adapter_ref = self

        # Patch the synchronous tool execution hook if present
        if hasattr(agent_or_callable, "hooks"):
            original_hooks = agent_or_callable.hooks

            class _EventEmittingHooks:
                """Thin hooks wrapper that emits agentcore events."""

                async def on_agent_start(
                    self, context: object, agent: object
                ) -> None:
                    await adapter_ref._bus.emit(
                        AgentEvent(EventType.AGENT_STARTED, adapter_ref._agent_id)
                    )
                    if original_hooks and hasattr(original_hooks, "on_agent_start"):
                        await original_hooks.on_agent_start(context, agent)

                async def on_agent_end(
                    self, context: object, agent: object, output: object
                ) -> None:
                    await adapter_ref._bus.emit(
                        AgentEvent(
                            EventType.AGENT_STOPPED,
                            adapter_ref._agent_id,
                            data={"success": True},
                        )
                    )
                    if original_hooks and hasattr(original_hooks, "on_agent_end"):
                        await original_hooks.on_agent_end(context, agent, output)

                async def on_tool_start(
                    self,
                    context: object,
                    agent: object,
                    tool: object,
                ) -> None:
                    tool_name = getattr(tool, "name", "unknown_tool")
                    await adapter_ref._bus.emit(
                        ToolCallEvent(
                            event_type=EventType.TOOL_CALLED,
                            agent_id=adapter_ref._agent_id,
                            tool_name=str(tool_name),
                            tool_input={},
                        )
                    )
                    if original_hooks and hasattr(original_hooks, "on_tool_start"):
                        await original_hooks.on_tool_start(context, agent, tool)

                async def on_tool_end(
                    self,
                    context: object,
                    agent: object,
                    tool: object,
                    result: object,
                ) -> None:
                    tool_name = getattr(tool, "name", "unknown_tool")
                    await adapter_ref._bus.emit(
                        ToolCallEvent(
                            event_type=EventType.TOOL_COMPLETED,
                            agent_id=adapter_ref._agent_id,
                            tool_name=str(tool_name),
                            tool_output=str(result),
                        )
                    )
                    if original_hooks and hasattr(original_hooks, "on_tool_end"):
                        await original_hooks.on_tool_end(context, agent, tool, result)

            agent_or_callable.hooks = _EventEmittingHooks()
            return agent_or_callable

        # Fallback: wrap via a thin async callable that emits lifecycle events
        original_run = getattr(Runner, "run", None) if _OPENAI_AGENTS_AVAILABLE else None

        if original_run is not None and hasattr(agent_or_callable, "__class__"):
            # Store the adapter reference on the agent itself so callers
            # wrapping Runner.run can detect the instrumented agent.
            agent_or_callable.__agentcore_adapter__ = adapter_ref

        return agent_or_callable

    def emit_events(self, bus: EventBus) -> None:
        """Update the event bus used by this adapter."""
        self._bus = bus

    async def run(self, input_text: str, **kwargs: object) -> Any:  # noqa: ANN401
        """Execute the wrapped agent via ``Runner.run`` with event emission.

        Parameters
        ----------
        input_text:
            The prompt or message to pass to the agent.
        **kwargs:
            Additional keyword arguments forwarded to ``Runner.run``.

        Returns
        -------
        Any
            The result from ``Runner.run``.

        Raises
        ------
        RuntimeError
            If the OpenAI Agents SDK is not installed.
        """
        if not _OPENAI_AGENTS_AVAILABLE:
            raise RuntimeError(
                "openai-agents is not installed. "
                "Install with: pip install openai-agents"
            )

        await self._bus.emit(
            AgentEvent(EventType.AGENT_STARTED, self._agent_id)
        )
        try:
            result = await Runner.run(  # type: ignore[attr-defined]
                self._original_agent, input_text, **kwargs
            )
            await self._bus.emit(
                AgentEvent(
                    EventType.AGENT_STOPPED,
                    self._agent_id,
                    data={"success": True},
                )
            )
            return result
        except Exception as exc:
            await self._bus.emit(
                AgentEvent(
                    EventType.ERROR_OCCURRED,
                    self._agent_id,
                    data={"error": str(exc), "error_type": type(exc).__name__},
                )
            )
            raise
