"""Anthropic SDK adapter for agentcore-sdk.

Emits ``AgentEvent`` objects by wrapping Anthropic ``Messages`` API calls
to capture message creation, tool use, and errors.  Degrades gracefully to a
no-op stub when ``anthropic`` is not installed.

Shipped in this module
----------------------
- AnthropicAdapter   — instruments Anthropic Messages API calls with event emission

Extension points
----------------
Streaming message capture, tool result correlation, and prompt caching telemetry
can be implemented as plugins using the adapter extension API.
"""
from __future__ import annotations

import logging
from typing import Any

from agentcore.adapters.base import FrameworkAdapter
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType, ToolCallEvent

logger = logging.getLogger(__name__)

# Optional Anthropic SDK import
try:
    import anthropic  # type: ignore[import-not-found]

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False
    anthropic = None  # type: ignore[assignment]


class AnthropicAdapter(FrameworkAdapter):
    """Instruments Anthropic SDK ``Messages`` API calls with ``AgentEvent`` emission.

    When ``anthropic`` is installed, :meth:`wrap` patches the ``messages.create``
    method on the provided client to emit ``AGENT_STARTED``, ``AGENT_STOPPED``,
    ``TOOL_CALLED``, and ``ERROR_OCCURRED`` events around each API call.

    When the SDK is absent, :meth:`wrap` returns the original object unchanged
    with a warning log.

    Parameters
    ----------
    agent_id:
        ID to associate with emitted events.
    bus:
        Event bus to emit on.

    Examples
    --------
    ::

        from agentcore.adapters.anthropic_sdk import AnthropicAdapter
        from agentcore.bus import EventBus

        bus = EventBus()
        adapter = AnthropicAdapter("my-claude-agent", bus)
        instrumented_client = adapter.wrap(anthropic.Anthropic())
        response = instrumented_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello!"}],
        )
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)
        self._original_create: Any = None

    def get_framework_name(self) -> str:
        return "anthropic"

    def wrap(self, agent_or_callable: Any) -> Any:  # noqa: ANN401
        """Patch the ``messages.create`` method on *agent_or_callable*.

        Parameters
        ----------
        agent_or_callable:
            An ``anthropic.Anthropic`` or ``anthropic.AsyncAnthropic`` client.

        Returns
        -------
        Any
            The same client object with a patched ``messages.create`` method,
            or unchanged if the Anthropic SDK is not installed.
        """
        if not _ANTHROPIC_AVAILABLE:
            logger.warning(
                "anthropic is not installed; AnthropicAdapter is a no-op. "
                "Install anthropic to enable Anthropic SDK event integration."
            )
            return agent_or_callable

        client = agent_or_callable
        adapter_ref = self

        if not hasattr(client, "messages"):
            logger.warning(
                "AnthropicAdapter.wrap() received an object with no 'messages' attribute; "
                "returning unchanged.  Pass an anthropic.Anthropic() client instance."
            )
            return client

        # Patch synchronous messages.create
        if hasattr(client.messages, "create"):
            original_create = client.messages.create

            def patched_create(*args: object, **kwargs: object) -> Any:  # noqa: ANN401
                adapter_ref._bus.emit_sync(
                    AgentEvent(EventType.AGENT_STARTED, adapter_ref._agent_id)
                )
                try:
                    response = original_create(*args, **kwargs)
                    adapter_ref._bus.emit_sync(
                        AgentEvent(
                            EventType.AGENT_STOPPED,
                            adapter_ref._agent_id,
                            data={"success": True},
                        )
                    )
                    # Emit tool-use events for any tool_use blocks in the response
                    _emit_tool_use_events(response, adapter_ref)
                    # Emit cost event if usage data is present
                    _emit_cost_event(response, adapter_ref)
                    return response
                except Exception as exc:
                    adapter_ref._bus.emit_sync(
                        AgentEvent(
                            EventType.ERROR_OCCURRED,
                            adapter_ref._agent_id,
                            data={"error": str(exc), "error_type": type(exc).__name__},
                        )
                    )
                    raise

            client.messages.create = patched_create  # type: ignore[method-assign]

        # Patch asynchronous messages.create (AsyncAnthropic client)
        if hasattr(client.messages, "acreate") or (
            hasattr(client, "__class__")
            and "async" in type(client).__name__.lower()
            and hasattr(client.messages, "create")
        ):
            if hasattr(client.messages, "acreate"):
                original_acreate = client.messages.acreate

                async def patched_acreate(*args: object, **kwargs: object) -> Any:  # noqa: ANN401
                    await adapter_ref._bus.emit(
                        AgentEvent(EventType.AGENT_STARTED, adapter_ref._agent_id)
                    )
                    try:
                        response = await original_acreate(*args, **kwargs)
                        await adapter_ref._bus.emit(
                            AgentEvent(
                                EventType.AGENT_STOPPED,
                                adapter_ref._agent_id,
                                data={"success": True},
                            )
                        )
                        _emit_tool_use_events(response, adapter_ref)
                        _emit_cost_event(response, adapter_ref)
                        return response
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

                client.messages.acreate = patched_acreate  # type: ignore[method-assign]

        return client

    def emit_events(self, bus: EventBus) -> None:
        """Update the event bus used by this adapter."""
        self._bus = bus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_tool_use_events(response: object, adapter: AnthropicAdapter) -> None:
    """Emit ``TOOL_CALLED`` events for any ``tool_use`` blocks in a response."""
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            tool_name = getattr(block, "name", "unknown_tool")
            tool_input = getattr(block, "input", {})
            adapter._bus.emit_sync(
                ToolCallEvent(
                    event_type=EventType.TOOL_CALLED,
                    agent_id=adapter._agent_id,
                    tool_name=str(tool_name),
                    tool_input=dict(tool_input) if isinstance(tool_input, dict) else {},
                )
            )


def _emit_cost_event(response: object, adapter: AnthropicAdapter) -> None:
    """Emit a ``COST_INCURRED`` event from Anthropic usage metadata."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    adapter._bus.emit_sync(
        AgentEvent(
            EventType.COST_INCURRED,
            adapter._agent_id,
            data={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )
    )
