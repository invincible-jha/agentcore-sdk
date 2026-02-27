"""LangChain framework adapter for agentcore-sdk.

Integrates with LangChain's callback system to emit ``AgentEvent`` objects
for tool calls, agent steps, errors, and LLM usage.  The import of
``langchain_core`` is optional — the adapter degrades gracefully to a no-op
stub when LangChain is not installed.

Shipped in this module
----------------------
- LangChainAdapter   — wraps a LangChain runnable/agent chain with event emission

Extension points
----------------
Token-level streaming capture, multi-chain correlation, and LangSmith
integration shims can be implemented as plugins using the adapter extension API.
"""
from __future__ import annotations

import logging
from typing import Any, Union
from uuid import UUID

from agentcore.adapters.base import FrameworkAdapter
from agentcore.bus.event_bus import EventBus
from agentcore.schema.errors import AdapterError
from agentcore.schema.events import AgentEvent, EventType, ToolCallEvent

logger = logging.getLogger(__name__)

# Optional LangChain import
try:
    from langchain_core.callbacks.base import BaseCallbackHandler  # type: ignore[import-not-found]
    from langchain_core.outputs import LLMResult  # type: ignore[import-not-found]

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    BaseCallbackHandler = object  # type: ignore[misc, assignment]
    LLMResult = object  # type: ignore[assignment]


class _AgentCoreCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    """LangChain callback handler that forwards events to an ``EventBus``.

    This is an internal implementation detail; consumers interact with
    :class:`LangChainAdapter`.
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        if _LANGCHAIN_AVAILABLE:
            super().__init__()
        self._agent_id = agent_id
        self._bus = bus

    # ------------------------------------------------------------------
    # Chain lifecycle
    # ------------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._bus.emit_sync(
            AgentEvent(
                EventType.AGENT_STARTED,
                self._agent_id,
                data={"run_id": str(run_id), "inputs": inputs},
            )
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._bus.emit_sync(
            AgentEvent(
                EventType.AGENT_STOPPED,
                self._agent_id,
                data={"run_id": str(run_id), "outputs": outputs, "success": True},
            )
        )

    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._bus.emit_sync(
            AgentEvent(
                EventType.ERROR_OCCURRED,
                self._agent_id,
                data={
                    "run_id": str(run_id),
                    "error": str(error),
                    "error_type": type(error).__name__,
                },
            )
        )

    # ------------------------------------------------------------------
    # Tool lifecycle
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        self._bus.emit_sync(
            ToolCallEvent(
                event_type=EventType.TOOL_CALLED,
                agent_id=self._agent_id,
                tool_name=str(tool_name),
                tool_input={"input": input_str},
                data={"run_id": str(run_id)},
            )
        )

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._bus.emit_sync(
            ToolCallEvent(
                event_type=EventType.TOOL_COMPLETED,
                agent_id=self._agent_id,
                tool_name="",
                tool_output=output,
                data={"run_id": str(run_id)},
            )
        )

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._bus.emit_sync(
            ToolCallEvent(
                event_type=EventType.TOOL_FAILED,
                agent_id=self._agent_id,
                tool_name="",
                tool_output=str(error),
                data={
                    "run_id": str(run_id),
                    "error": str(error),
                    "error_type": type(error).__name__,
                },
            )
        )

    # ------------------------------------------------------------------
    # LLM lifecycle (cost-tracking bridge)
    # ------------------------------------------------------------------

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        # Attempt to extract token usage from LLM response metadata
        usage: dict[str, object] = {}
        if hasattr(response, "llm_output") and isinstance(response.llm_output, dict):
            token_usage = response.llm_output.get("token_usage", {})
            if isinstance(token_usage, dict):
                usage = {
                    "input_tokens": token_usage.get("prompt_tokens", 0),
                    "output_tokens": token_usage.get("completion_tokens", 0),
                }
        self._bus.emit_sync(
            AgentEvent(
                EventType.COST_INCURRED,
                self._agent_id,
                data={"run_id": str(run_id), **usage},
            )
        )


class LangChainAdapter(FrameworkAdapter):
    """Instruments a LangChain runnable / chain with ``AgentEvent`` emission.

    When ``langchain_core`` is installed the adapter injects an
    ``_AgentCoreCallbackHandler`` into the chain's callback list.
    When LangChain is absent the adapter logs a warning and returns the
    original object unchanged from :meth:`wrap`.

    Parameters
    ----------
    agent_id:
        ID to associate with emitted events.
    bus:
        Event bus to emit on.

    Examples
    --------
    ::

        from agentcore.adapters.langchain import LangChainAdapter
        from agentcore.bus import EventBus

        bus = EventBus()
        adapter = LangChainAdapter("my-lc-agent", bus)
        wrapped_chain = adapter.wrap(my_chain)
        # wrapped_chain now emits AgentEvents on every invocation
    """

    def __init__(self, agent_id: str, bus: EventBus) -> None:
        super().__init__(agent_id, bus)
        self._handler: _AgentCoreCallbackHandler | None = None

    def get_framework_name(self) -> str:
        return "langchain"

    def wrap(self, agent_or_callable: Any) -> Any:  # noqa: ANN401
        """Attach the callback handler to *agent_or_callable*.

        Parameters
        ----------
        agent_or_callable:
            A LangChain ``Runnable``, chain, or agent executor.

        Returns
        -------
        Any
            The same object with the callback handler attached, or the
            unchanged object if LangChain is not installed.

        Raises
        ------
        AdapterError
            If the object has no ``.callbacks`` attribute and LangChain is
            installed (unexpected interface).
        """
        if not _LANGCHAIN_AVAILABLE:
            logger.warning(
                "langchain_core is not installed; LangChainAdapter is a no-op. "
                "Install langchain-core to enable LangChain event integration."
            )
            return agent_or_callable

        self._handler = _AgentCoreCallbackHandler(
            agent_id=self._agent_id,
            bus=self._bus,
        )

        # LangChain runnables accept callbacks via .with_config()
        if hasattr(agent_or_callable, "with_config"):
            return agent_or_callable.with_config(
                {"callbacks": [self._handler]}
            )

        # Fallback: try to append to existing callbacks list
        if hasattr(agent_or_callable, "callbacks"):
            callbacks = getattr(agent_or_callable, "callbacks") or []
            if isinstance(callbacks, list):
                callbacks.append(self._handler)
                agent_or_callable.callbacks = callbacks
            return agent_or_callable

        raise AdapterError(
            "LangChainAdapter.wrap() could not attach callbacks: "
            "the provided object has no 'callbacks' attribute or 'with_config' method.",
            context={"type": type(agent_or_callable).__name__},
        )

    def emit_events(self, bus: EventBus) -> None:
        """Update the event bus used by the attached callback handler."""
        self._bus = bus
        if self._handler is not None:
            self._handler._bus = bus
