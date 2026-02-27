"""Subscriber protocol and filter wrapper for agentcore event bus.

Shipped in this module
----------------------
- Subscriber          — structural Protocol for event handler callables
- FilteredSubscriber  — wraps any handler with an EventFilter gate

Extension points
-------------------
Back-pressure aware subscribers, durable subscriptions with at-least-once
delivery, and fan-out load balancing are available via plugins.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentcore.bus.filters import EventFilter
from agentcore.schema.events import AgentEvent


@runtime_checkable
class Subscriber(Protocol):
    """Structural protocol satisfied by any callable that accepts an event.

    Both sync and async callables are accepted by the event bus.  This
    protocol defines the expected signature for static type checkers.

    Examples
    --------
    Any function with the right signature automatically satisfies this
    protocol::

        def my_handler(event: AgentEvent) -> None:
            print(event.event_type)

        assert isinstance(my_handler, Subscriber)
    """

    def __call__(self, event: AgentEvent) -> object:
        """Handle a single agent event.

        Parameters
        ----------
        event:
            The event to handle.  Must not be mutated.
        """
        ...


class FilteredSubscriber:
    """Wraps a handler so that it is only called when a filter passes.

    Parameters
    ----------
    handler:
        The underlying event handler.  May be sync or async.
    event_filter:
        The filter gate.  Only events for which
        ``event_filter.matches(event)`` returns ``True`` reach the handler.

    Examples
    --------
    >>> from agentcore.bus.filters import TypeFilter
    >>> from agentcore.schema.events import EventType, AgentEvent
    >>> received: list[AgentEvent] = []
    >>> fs = FilteredSubscriber(
    ...     handler=received.append,
    ...     event_filter=TypeFilter(EventType.TOOL_CALLED),
    ... )
    >>> fs(AgentEvent(EventType.AGENT_STARTED, "agent-1"))  # filtered out
    >>> fs(AgentEvent(EventType.TOOL_CALLED, "agent-1"))    # forwarded
    >>> len(received)
    1
    """

    def __init__(self, handler: Subscriber, event_filter: EventFilter) -> None:
        self._handler = handler
        self._filter = event_filter

    def __call__(self, event: AgentEvent) -> object:
        """Invoke the wrapped handler only if the filter matches.

        Parameters
        ----------
        event:
            Candidate event.

        Returns
        -------
        object
            Whatever the wrapped handler returns, or ``None`` if filtered out.
        """
        if self._filter.matches(event):
            return self._handler(event)
        return None

    def __repr__(self) -> str:
        return (
            f"FilteredSubscriber(handler={self._handler!r}, "
            f"filter={self._filter!r})"
        )
