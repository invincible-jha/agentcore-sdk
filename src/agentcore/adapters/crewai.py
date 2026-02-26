"""CrewAI framework adapter for agentcore-sdk.

Emits ``AgentEvent`` objects by monkey-patching the crew's ``kickoff`` method
(and agent task execution methods) when CrewAI is installed.  Degrades
gracefully to a no-op stub when ``crewai`` is not installed.

Shipped in this module
----------------------
- CrewAIAdapter   — instruments a CrewAI ``Crew`` with event emission

Withheld / internal
-------------------
Per-task cost attribution, hierarchical crew event correlation, and CrewAI
Flow event mapping are available via plugins.
"""
from __future__ import annotations

import logging
from typing import Any

from agentcore.adapters.base import FrameworkAdapter
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType

logger = logging.getLogger(__name__)

# Optional CrewAI import
try:
    import crewai  # type: ignore[import-not-found]

    _CREWAI_AVAILABLE = True
except ImportError:
    _CREWAI_AVAILABLE = False
    crewai = None  # type: ignore[assignment]


class CrewAIAdapter(FrameworkAdapter):
    """Instruments a CrewAI ``Crew`` object with ``AgentEvent`` emission.

    When ``crewai`` is installed, :meth:`wrap` patches the crew's
    ``kickoff`` (and ``kickoff_async``) method with thin wrappers that emit
    ``AGENT_STARTED`` / ``AGENT_STOPPED`` / ``ERROR_OCCURRED`` events.

    When CrewAI is not installed, :meth:`wrap` returns the original object
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

        from agentcore.adapters.crewai import CrewAIAdapter
        from agentcore.bus import EventBus

        bus = EventBus()
        adapter = CrewAIAdapter("my-crew", bus)
        instrumented_crew = adapter.wrap(my_crew)
        result = instrumented_crew.kickoff()
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)
        self._original_kickoff: Any = None
        self._original_kickoff_async: Any = None

    def get_framework_name(self) -> str:
        return "crewai"

    def wrap(self, agent_or_callable: Any) -> Any:  # noqa: ANN401
        """Patch *agent_or_callable* (a ``Crew``) with event emission.

        Parameters
        ----------
        agent_or_callable:
            A ``crewai.Crew`` instance.

        Returns
        -------
        Any
            The same object with patched ``kickoff`` / ``kickoff_async``
            methods, or unchanged if CrewAI is not installed.
        """
        if not _CREWAI_AVAILABLE:
            logger.warning(
                "crewai is not installed; CrewAIAdapter is a no-op. "
                "Install crewai to enable CrewAI event integration."
            )
            return agent_or_callable

        crew = agent_or_callable
        adapter_ref = self

        # Patch synchronous kickoff
        if hasattr(crew, "kickoff"):
            original_kickoff = crew.kickoff

            def patched_kickoff(*args: object, **kwargs: object) -> Any:  # noqa: ANN401
                adapter_ref._bus.emit_sync(
                    AgentEvent(EventType.AGENT_STARTED, adapter_ref._agent_id)
                )
                try:
                    result = original_kickoff(*args, **kwargs)
                    adapter_ref._bus.emit_sync(
                        AgentEvent(
                            EventType.AGENT_STOPPED,
                            adapter_ref._agent_id,
                            data={"success": True},
                        )
                    )
                    return result
                except Exception as exc:
                    adapter_ref._bus.emit_sync(
                        AgentEvent(
                            EventType.ERROR_OCCURRED,
                            adapter_ref._agent_id,
                            data={"error": str(exc), "error_type": type(exc).__name__},
                        )
                    )
                    raise

            crew.kickoff = patched_kickoff

        # Patch async kickoff_async if present
        if hasattr(crew, "kickoff_async"):
            original_kickoff_async = crew.kickoff_async

            async def patched_kickoff_async(*args: object, **kwargs: object) -> Any:  # noqa: ANN401
                await adapter_ref._bus.emit(
                    AgentEvent(EventType.AGENT_STARTED, adapter_ref._agent_id)
                )
                try:
                    result = await original_kickoff_async(*args, **kwargs)
                    await adapter_ref._bus.emit(
                        AgentEvent(
                            EventType.AGENT_STOPPED,
                            adapter_ref._agent_id,
                            data={"success": True},
                        )
                    )
                    return result
                except Exception as exc:
                    await adapter_ref._bus.emit(
                        AgentEvent(
                            EventType.ERROR_OCCURRED,
                            adapter_ref._agent_id,
                            data={"error": str(exc), "error_type": type(exc).__name__},
                        )
                    )
                    raise

            crew.kickoff_async = patched_kickoff_async

        return crew

    def emit_events(self, bus: EventBus) -> None:
        """Update the event bus used by this adapter's patched methods."""
        self._bus = bus
