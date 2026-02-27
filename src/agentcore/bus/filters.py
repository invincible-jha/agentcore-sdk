"""Event filter primitives for agentcore-sdk.

Filters are composable predicates applied by ``FilteredSubscriber`` before a
handler is invoked.  They allow subscribers to express interest in a precise
slice of the event stream without the handler itself needing branching logic.

Shipped in this module
----------------------
- FilterMode          — ALL / ANY combinator enum
- EventFilter         — ABC for all filters
- TypeFilter          — match by EventType
- AgentFilter         — match by agent_id
- MetadataFilter      — match by metadata key/value pair
- CompositeFilter     — combine multiple filters with AND / OR semantics

Extension points
-------------------
Content-based routing, CEP (complex event processing) patterns, and
Kafka/Pulsar topic mapping are available via plugins.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from agentcore.schema.events import AgentEvent, EventType


class FilterMode(str, Enum):
    """Combinator mode for :class:`CompositeFilter`."""

    ALL = "all"  # logical AND — every sub-filter must match
    ANY = "any"  # logical OR  — at least one sub-filter must match


class EventFilter(ABC):
    """Abstract base class for event filters.

    A filter is a pure predicate: it takes an :class:`AgentEvent` and returns
    ``True`` if the event should be forwarded to the subscriber.
    """

    @abstractmethod
    def matches(self, event: AgentEvent) -> bool:
        """Return ``True`` if *event* passes this filter.

        Parameters
        ----------
        event:
            The candidate event to evaluate.

        Returns
        -------
        bool
        """

    def __and__(self, other: "EventFilter") -> "CompositeFilter":
        """Combine two filters with AND semantics via the ``&`` operator."""
        return CompositeFilter(filters=[self, other], mode=FilterMode.ALL)

    def __or__(self, other: "EventFilter") -> "CompositeFilter":
        """Combine two filters with OR semantics via the ``|`` operator."""
        return CompositeFilter(filters=[self, other], mode=FilterMode.ANY)


class TypeFilter(EventFilter):
    """Accept events whose ``event_type`` is in the allowed set.

    Parameters
    ----------
    event_types:
        One or more :class:`~agentcore.schema.events.EventType` values.

    Examples
    --------
    >>> f = TypeFilter(EventType.TOOL_CALLED, EventType.TOOL_COMPLETED)
    >>> f.matches(AgentEvent(EventType.TOOL_CALLED, "agent-1"))
    True
    """

    def __init__(self, *event_types: EventType) -> None:
        self._types: frozenset[EventType] = frozenset(event_types)

    def matches(self, event: AgentEvent) -> bool:
        return event.event_type in self._types

    def __repr__(self) -> str:
        names = ", ".join(t.value for t in sorted(self._types, key=lambda t: t.value))
        return f"TypeFilter({names})"


class AgentFilter(EventFilter):
    """Accept events originating from the specified agent IDs.

    Parameters
    ----------
    agent_ids:
        One or more agent ID strings.

    Examples
    --------
    >>> f = AgentFilter("agent-1", "agent-2")
    >>> f.matches(AgentEvent(EventType.AGENT_STARTED, "agent-1"))
    True
    """

    def __init__(self, *agent_ids: str) -> None:
        self._agent_ids: frozenset[str] = frozenset(agent_ids)

    def matches(self, event: AgentEvent) -> bool:
        return event.agent_id in self._agent_ids

    def __repr__(self) -> str:
        return f"AgentFilter({sorted(self._agent_ids)!r})"


class MetadataFilter(EventFilter):
    """Accept events whose ``metadata`` dict contains a matching key/value.

    Parameters
    ----------
    key:
        The metadata key to look up.
    value:
        The expected value.  Comparison uses ``==``.

    Examples
    --------
    >>> evt = AgentEvent(EventType.CUSTOM, "a1", metadata={"env": "prod"})
    >>> MetadataFilter("env", "prod").matches(evt)
    True
    """

    def __init__(self, key: str, value: object) -> None:
        self._key = key
        self._value = value

    def matches(self, event: AgentEvent) -> bool:
        return event.metadata.get(self._key) == self._value

    def __repr__(self) -> str:
        return f"MetadataFilter(key={self._key!r}, value={self._value!r})"


class CompositeFilter(EventFilter):
    """Combine multiple filters with AND or OR semantics.

    Parameters
    ----------
    filters:
        The child filters to evaluate.
    mode:
        ``FilterMode.ALL`` requires every filter to match (AND);
        ``FilterMode.ANY`` requires at least one to match (OR).

    Examples
    --------
    >>> f = TypeFilter(EventType.TOOL_CALLED) & AgentFilter("agent-1")
    >>> isinstance(f, CompositeFilter)
    True
    """

    def __init__(
        self,
        filters: list[EventFilter],
        mode: FilterMode = FilterMode.ALL,
    ) -> None:
        self._filters = list(filters)
        self._mode = mode

    def matches(self, event: AgentEvent) -> bool:
        if self._mode is FilterMode.ALL:
            return all(f.matches(event) for f in self._filters)
        return any(f.matches(event) for f in self._filters)

    def __repr__(self) -> str:
        combinator = " AND " if self._mode is FilterMode.ALL else " OR "
        inner = combinator.join(repr(f) for f in self._filters)
        return f"CompositeFilter({inner!r})"
