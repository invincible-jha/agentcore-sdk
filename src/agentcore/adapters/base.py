"""Framework adapter base for agentcore-sdk.

Adapters intercept agent calls from third-party frameworks and translate
them into ``AgentEvent`` objects emitted onto an ``EventBus``.

Shipped in this module
----------------------
- FrameworkAdapter   — ABC for all framework adapters

Extension points
----------------
Streaming response adapters, multi-modal event capture, and distributed
trace correlation across adapter boundaries can be implemented as plugins
using the adapter extension API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentcore.bus.event_bus import EventBus
from agentcore.schema.errors import AdapterError


class FrameworkAdapter(ABC):
    """Abstract base class for framework-specific agent adapters.

    An adapter wraps an agent object (or callable) to intercept its calls
    and emit structured ``AgentEvent`` objects onto a shared ``EventBus``.

    Subclasses must implement :meth:`wrap`, :meth:`get_framework_name`, and
    :meth:`emit_events`.

    Parameters
    ----------
    agent_id:
        The ID of the agent this adapter is associated with.
    bus:
        The ``EventBus`` instance that events will be emitted to.

    Examples
    --------
    Implement a minimal adapter::

        class MyAdapter(FrameworkAdapter):
            def get_framework_name(self) -> str:
                return "my-framework"

            def wrap(self, agent_or_callable):
                # instrument and return the wrapped agent
                ...

            def emit_events(self, bus):
                self._bus = bus
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        self._agent_id = agent_id
        self._bus = bus

    @property
    def agent_id(self) -> str:
        """The agent ID this adapter emits events for."""
        return self._agent_id

    @abstractmethod
    def get_framework_name(self) -> str:
        """Return the canonical name of the wrapped framework.

        Returns
        -------
        str
            E.g. ``"langchain"``, ``"crewai"``, ``"callable"``.
        """

    @abstractmethod
    def wrap(self, agent_or_callable: Any) -> Any:  # noqa: ANN401
        """Instrument *agent_or_callable* and return the wrapped version.

        The returned object should be a drop-in replacement for the
        original — callers should be able to use it without knowing it is
        instrumented.

        Parameters
        ----------
        agent_or_callable:
            The agent object or callable to instrument.

        Returns
        -------
        Any
            The instrumented version.

        Raises
        ------
        AdapterError
            If the provided object is incompatible with this adapter.
        """

    @abstractmethod
    def emit_events(self, bus: EventBus) -> None:
        """Attach (or update) the event bus used by this adapter.

        Calling this method after ``wrap`` changes the bus that events are
        emitted to, enabling runtime bus switching.

        Parameters
        ----------
        bus:
            The new ``EventBus`` to emit events on.
        """

    def _require_compatible(self, obj: object, expected_type: type) -> None:
        """Assert *obj* is an instance of *expected_type*.

        Parameters
        ----------
        obj:
            Object to check.
        expected_type:
            The required type.

        Raises
        ------
        AdapterError
            If *obj* is not an instance of *expected_type*.
        """
        if not isinstance(obj, expected_type):
            raise AdapterError(
                f"{self.get_framework_name()} adapter expected "
                f"{expected_type.__name__} but got {type(obj).__name__}.",
                context={"framework": self.get_framework_name()},
            )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"framework={self.get_framework_name()!r}, "
            f"agent_id={self._agent_id!r})"
        )
