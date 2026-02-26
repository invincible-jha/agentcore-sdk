"""Callable adapter for agentcore-sdk.

Wraps any sync or async callable to emit ``AgentEvent`` objects before and
after each invocation.  No third-party dependencies required.

Shipped in this module
----------------------
- CallableAdapter   — wraps any sync/async callable with event emission

Withheld / internal
-------------------
Retry/back-pressure-aware wrappers and structured output extraction are
available via plugins.
"""
from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from agentcore.adapters.base import FrameworkAdapter
from agentcore.bus.event_bus import EventBus
from agentcore.schema.errors import AdapterError
from agentcore.schema.events import AgentEvent, EventType

logger = logging.getLogger(__name__)


class CallableAdapter(FrameworkAdapter):
    """Wraps any sync or async callable to emit :class:`AgentEvent` objects.

    On each call the adapter emits:

    - ``AGENT_STARTED`` before invoking the callable
    - ``AGENT_STOPPED`` after a successful return
    - ``ERROR_OCCURRED`` if the callable raises

    Tool-level events (``TOOL_CALLED`` / ``TOOL_COMPLETED`` / ``TOOL_FAILED``)
    are *not* emitted by this adapter because a plain callable has no notion
    of tools — use the LangChain or CrewAI adapters for richer instrumentation.

    Parameters
    ----------
    agent_id:
        ID to associate with emitted events.
    bus:
        The event bus to emit on.

    Examples
    --------
    >>> import asyncio
    >>> bus = EventBus()
    >>> events = []
    >>> bus.subscribe_all(events.append)
    ...
    >>> def my_fn(x: int) -> int:
    ...     return x * 2
    >>> adapter = CallableAdapter("agent-1", bus)
    >>> wrapped = adapter.wrap(my_fn)
    >>> result = asyncio.run(wrapped(5))
    >>> result
    10
    >>> len(events) >= 2
    True
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)
        self._wrapped: Callable[..., Any] | None = None

    def get_framework_name(self) -> str:
        return "callable"

    def wrap(self, agent_or_callable: Any) -> Any:  # noqa: ANN401
        """Instrument *agent_or_callable* with event emission.

        Parameters
        ----------
        agent_or_callable:
            Any sync or async callable.

        Returns
        -------
        Callable
            An async wrapper that emits events around the original call.

        Raises
        ------
        AdapterError
            If *agent_or_callable* is not callable.
        """
        if not callable(agent_or_callable):
            raise AdapterError(
                f"CallableAdapter.wrap() requires a callable; "
                f"got {type(agent_or_callable).__name__}.",
                context={"framework": self.get_framework_name()},
            )
        self._wrapped = agent_or_callable
        is_async = inspect.iscoroutinefunction(agent_or_callable)

        adapter_ref = self

        if is_async:
            async def async_wrapper(*args: object, **kwargs: object) -> Any:  # noqa: ANN401
                return await adapter_ref._invoke_async(agent_or_callable, args, kwargs)

            return async_wrapper
        else:
            async def sync_wrapper(*args: object, **kwargs: object) -> Any:  # noqa: ANN401
                return await adapter_ref._invoke_sync(agent_or_callable, args, kwargs)

            return sync_wrapper

    def emit_events(self, bus: EventBus) -> None:
        """Swap the event bus used by this adapter.

        Parameters
        ----------
        bus:
            The replacement event bus.
        """
        self._bus = bus

    # ------------------------------------------------------------------
    # Internal invocation helpers
    # ------------------------------------------------------------------

    async def _invoke_async(
        self,
        fn: Callable[..., Any],
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> Any:  # noqa: ANN401
        """Async invocation path with event emission."""
        await self._bus.emit(AgentEvent(EventType.AGENT_STARTED, self._agent_id))
        try:
            result = await fn(*args, **kwargs)
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

    async def _invoke_sync(
        self,
        fn: Callable[..., Any],
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> Any:  # noqa: ANN401
        """Sync invocation path with event emission."""
        await self._bus.emit(AgentEvent(EventType.AGENT_STARTED, self._agent_id))
        try:
            result = fn(*args, **kwargs)
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
