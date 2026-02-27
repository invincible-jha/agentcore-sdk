"""Framework bridge abstract base class.

A :class:`FrameworkBridge` converts framework-native event payloads into
agentcore :class:`~agentcore.schema.events.AgentEvent` objects and emits them
on a shared :class:`~agentcore.bus.event_bus.EventBus`.

This is distinct from the existing :class:`~agentcore.adapters.base.FrameworkAdapter`
in that bridges do not wrap agent callables — they translate discrete event
payloads on demand.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent


class FrameworkBridge(ABC):
    """Abstract base for framework event bridges.

    Subclasses implement :meth:`adapt_event` to convert a framework-specific
    event payload into an :class:`AgentEvent`, and :meth:`emit_event` to
    publish to the bus.

    Parameters
    ----------
    agent_id:
        The agent identifier to attach to all emitted events.
    bus:
        The :class:`EventBus` to publish events on.
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        self._agent_id = agent_id
        self._bus = bus

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def supported_framework(self) -> str:
        """Return the canonical framework name this bridge supports.

        Returns
        -------
        str
            E.g. ``"langchain"``, ``"crewai"``, ``"autogen"``.
        """

    @abstractmethod
    def adapt_event(self, framework_event: Any) -> AgentEvent | None:
        """Convert a framework-native event to an :class:`AgentEvent`.

        Parameters
        ----------
        framework_event:
            A raw event payload from the target framework.

        Returns
        -------
        AgentEvent | None
            The adapted event, or None if the payload should be ignored.
        """

    # ------------------------------------------------------------------
    # Concrete methods
    # ------------------------------------------------------------------

    def emit_event(self, framework_event: Any) -> AgentEvent | None:
        """Adapt and emit *framework_event* on the bus.

        Calls :meth:`adapt_event` and publishes the result if not None.

        Parameters
        ----------
        framework_event:
            A raw event payload from the target framework.

        Returns
        -------
        AgentEvent | None
            The emitted event, or None if the event was ignored.
        """
        agent_event = self.adapt_event(framework_event)
        if agent_event is not None:
            self._bus.emit_sync(agent_event)
        return agent_event

    def emit_batch(self, framework_events: list[Any]) -> list[AgentEvent]:
        """Adapt and emit multiple framework events.

        Parameters
        ----------
        framework_events:
            List of raw event payloads.

        Returns
        -------
        list[AgentEvent]
            All non-None adapted events that were published.
        """
        published: list[AgentEvent] = []
        for raw in framework_events:
            result = self.emit_event(raw)
            if result is not None:
                published.append(result)
        return published

    @property
    def agent_id(self) -> str:
        """Return the agent ID this bridge emits events for."""
        return self._agent_id

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"framework={self.supported_framework!r}, "
            f"agent_id={self._agent_id!r})"
        )


__all__ = ["FrameworkBridge"]
