"""In-process event bus for agentcore-sdk.

The ``EventBus`` is the central pub/sub backbone that lets every component of
an agent system observe and react to lifecycle events without direct coupling.

Shipped in this module
----------------------
- EventBus     — thread-safe pub/sub bus with async emit, sync wrapper,
                 event history, and exception-safe dispatch

Withheld / internal
-------------------
Persistent event log replay, distributed fan-out over message brokers
(Kafka, Pulsar, Redis Streams), and dead-letter queue handling are
available via plugins.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import uuid
from collections import deque
from typing import Callable

from agentcore.bus.subscriber import Subscriber
from agentcore.schema.errors import EventBusError
from agentcore.schema.events import AgentEvent, EventType

logger = logging.getLogger(__name__)

# Type alias for the handler callable stored in the registry
_Handler = Callable[[AgentEvent], object]


class EventBus:
    """Thread-safe, in-process publish/subscribe event bus.

    Subscribers register interest in specific ``EventType`` values or in
    *all* events.  When an event is emitted the bus dispatches it to every
    matching subscriber, protecting the caller from any handler exceptions.

    Parameters
    ----------
    max_history:
        Maximum number of events retained in the in-memory history buffer.
        Set to ``0`` to disable history.  Defaults to ``1000``.

    Examples
    --------
    >>> import asyncio
    >>> bus = EventBus()
    >>> received = []
    >>> sub_id = bus.subscribe(EventType.AGENT_STARTED, received.append)
    >>> asyncio.run(bus.emit(AgentEvent(EventType.AGENT_STARTED, "a1")))
    >>> len(received)
    1
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = threading.Lock()
        # Map from EventType -> {subscription_id: handler}
        self._type_subscribers: dict[EventType, dict[str, _Handler]] = {}
        # Global subscribers interested in every event
        self._global_subscribers: dict[str, _Handler] = {}
        self._max_history = max_history
        self._history: deque[AgentEvent] = deque(maxlen=max_history if max_history > 0 else None)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, event_type: EventType, handler: Subscriber) -> str:
        """Register *handler* to receive events of a specific type.

        Parameters
        ----------
        event_type:
            The :class:`~agentcore.schema.events.EventType` to subscribe to.
        handler:
            Callable that accepts an :class:`~agentcore.schema.events.AgentEvent`.
            May be sync or async.

        Returns
        -------
        str
            Opaque subscription ID.  Pass to :meth:`unsubscribe` to cancel.

        Raises
        ------
        EventBusError
            If ``event_type`` is not a valid ``EventType``.
        """
        if not isinstance(event_type, EventType):
            raise EventBusError(
                f"Invalid event_type {event_type!r}; must be an EventType enum member."
            )
        sub_id = str(uuid.uuid4())
        with self._lock:
            if event_type not in self._type_subscribers:
                self._type_subscribers[event_type] = {}
            self._type_subscribers[event_type][sub_id] = handler  # type: ignore[assignment]
        logger.debug("Subscribed %s to %s (id=%s)", handler, event_type.value, sub_id)
        return sub_id

    def subscribe_all(self, handler: Subscriber) -> str:
        """Register *handler* to receive every event regardless of type.

        Parameters
        ----------
        handler:
            Callable that accepts an :class:`~agentcore.schema.events.AgentEvent`.

        Returns
        -------
        str
            Subscription ID for use with :meth:`unsubscribe`.
        """
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._global_subscribers[sub_id] = handler  # type: ignore[assignment]
        logger.debug("Subscribed %s to ALL events (id=%s)", handler, sub_id)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Cancel a subscription by its ID.

        Parameters
        ----------
        subscription_id:
            The ID returned by :meth:`subscribe` or :meth:`subscribe_all`.

        Raises
        ------
        EventBusError
            If ``subscription_id`` is not found in any subscriber map.
        """
        with self._lock:
            # Check global subscribers first
            if subscription_id in self._global_subscribers:
                del self._global_subscribers[subscription_id]
                logger.debug("Unsubscribed global handler id=%s", subscription_id)
                return
            # Check type-specific subscribers
            for type_map in self._type_subscribers.values():
                if subscription_id in type_map:
                    del type_map[subscription_id]
                    logger.debug("Unsubscribed type handler id=%s", subscription_id)
                    return
        raise EventBusError(
            f"Subscription {subscription_id!r} not found; it may have already been cancelled."
        )

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    async def emit(self, event: AgentEvent) -> None:
        """Dispatch *event* to all matching subscribers asynchronously.

        Collects the relevant handlers under the lock, then releases the
        lock before invoking them so that handlers may themselves call
        ``subscribe`` or ``emit`` without deadlocking.

        Async handlers are awaited; sync handlers are called directly.
        All handler exceptions are caught and logged — a misbehaving
        subscriber never prevents other subscribers from receiving the event.

        Parameters
        ----------
        event:
            The event to dispatch.
        """
        with self._lock:
            # Snapshot the handlers for this event type + global handlers
            type_handlers = list(
                self._type_subscribers.get(event.event_type, {}).values()
            )
            global_handlers = list(self._global_subscribers.values())
            if self._max_history != 0:
                self._history.append(event)

        all_handlers: list[_Handler] = type_handlers + global_handlers
        for handler in all_handlers:
            await self._safe_call(handler, event)

    def emit_sync(self, event: AgentEvent) -> None:
        """Synchronous wrapper around :meth:`emit`.

        Runs the async emit coroutine on an existing event loop if one is
        running, or spins up a new one.  Prefer :meth:`emit` in async
        contexts.

        Parameters
        ----------
        event:
            The event to dispatch.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # We are already inside an async context — schedule the coroutine
            # as a task so it doesn't block the caller.
            loop.create_task(self.emit(event))
        else:
            asyncio.run(self.emit(event))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _safe_call(self, handler: _Handler, event: AgentEvent) -> None:
        """Invoke *handler* with *event*, absorbing all exceptions.

        Async handlers are awaited; sync handlers are called synchronously.
        Any exception is logged at ERROR level and suppressed so that
        downstream subscribers still receive the event.

        Parameters
        ----------
        handler:
            The subscriber callable.
        event:
            The event to pass.
        """
        try:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception(
                "Unhandled exception in event handler %r for event %s (id=%s)",
                handler,
                event.event_type.value,
                event.event_id,
            )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self) -> list[AgentEvent]:
        """Return a snapshot of the event history buffer.

        Returns
        -------
        list[AgentEvent]
            Events in emission order, oldest first.  The list is a copy;
            mutations do not affect the internal buffer.
        """
        with self._lock:
            return list(self._history)

    def clear_history(self) -> None:
        """Discard all events in the history buffer."""
        with self._lock:
            self._history.clear()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def subscriber_count(self) -> int:
        """Return the total number of active subscriptions."""
        with self._lock:
            type_count = sum(len(v) for v in self._type_subscribers.values())
            return type_count + len(self._global_subscribers)

    def __repr__(self) -> str:
        return (
            f"EventBus(subscribers={self.subscriber_count()}, "
            f"history_size={len(self._history)}, "
            f"max_history={self._max_history})"
        )
