"""Convenience API for agentcore-sdk — 3-line quickstart.

Example
-------
::

    from agentcore import AgentCore, Event
    core = AgentCore()
    event = Event("agent.started", {"agent_id": "my-agent"})

"""
from __future__ import annotations

from typing import Any


class AgentCore:
    """Zero-config AgentCore wrapper for the 80% use case.

    Initialises an EventBus, an AgentRegistry, and a NullExporter
    so the SDK is ready to use immediately with no configuration.

    Example
    -------
    ::

        from agentcore import AgentCore, Event
        core = AgentCore()
        core.emit(Event("agent.started", {"agent_id": "demo"}))
    """

    def __init__(self) -> None:
        from agentcore.bus.event_bus import EventBus
        from agentcore.identity.registry import AgentRegistry
        from agentcore.telemetry.collector import MetricCollector

        self.bus: EventBus = EventBus()
        self.registry: AgentRegistry = AgentRegistry()
        self.metrics: MetricCollector = MetricCollector()

    def emit(self, event: "Event") -> None:
        """Emit an event on the bus synchronously.

        Parameters
        ----------
        event:
            The Event to emit.
        """
        import asyncio
        asyncio.run(self.bus.emit(event._inner))

    def subscribe(self, event_type: str, handler: Any) -> str:
        """Subscribe a handler for a named event type.

        Parameters
        ----------
        event_type:
            Event type string (e.g. ``"agent.started"``).
        handler:
            Callable invoked with each matching AgentEvent.

        Returns
        -------
        str
            Subscription ID that can be used to unsubscribe.
        """
        from agentcore.schema.events import EventType
        try:
            etype = EventType(event_type)
        except ValueError:
            etype = EventType.AGENT_STARTED  # fallback
        return self.bus.subscribe(etype, handler)

    def __repr__(self) -> str:
        return "AgentCore(bus=EventBus, registry=AgentRegistry)"


class Event:
    """Lightweight wrapper around AgentEvent for zero-boilerplate usage.

    Parameters
    ----------
    event_type:
        Event type string (e.g. ``"agent.started"``).
    data:
        Arbitrary metadata dict attached to the event.
    agent_id:
        Optional agent identifier.

    Example
    -------
    ::

        from agentcore import Event
        event = Event("agent.started", {"model": "claude-sonnet-4"})
    """

    def __init__(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        agent_id: str = "default-agent",
    ) -> None:
        from agentcore.schema.events import AgentEvent, EventType

        try:
            etype = EventType(event_type)
        except ValueError:
            etype = EventType.AGENT_STARTED

        self._inner = AgentEvent(
            event_type=etype,
            agent_id=agent_id,
            metadata=data or {},
        )
        self.event_type = event_type
        self.data = data or {}

    def __repr__(self) -> str:
        return f"Event(type={self.event_type!r}, data={self.data!r})"
