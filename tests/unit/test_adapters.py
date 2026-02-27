"""Unit tests for agentcore adapter modules.

Covers:
- adapters.base   — FrameworkAdapter ABC helpers
- adapters.callable — CallableAdapter sync and async wrapping
- adapters.crewai  — CrewAIAdapter with and without crewai installed
- adapters.langchain — LangChainAdapter with and without langchain installed
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from agentcore.adapters.base import FrameworkAdapter
from agentcore.adapters.callable import CallableAdapter
from agentcore.adapters.crewai import CrewAIAdapter
from agentcore.adapters.langchain import LangChainAdapter, _AgentCoreCallbackHandler
from agentcore.bus.event_bus import EventBus
from agentcore.schema.errors import AdapterError
from agentcore.schema.events import AgentEvent, EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_events(bus: EventBus) -> list[AgentEvent]:
    collected: list[AgentEvent] = []
    bus.subscribe_all(collected.append)
    return collected


# ---------------------------------------------------------------------------
# FrameworkAdapter — base
# ---------------------------------------------------------------------------

class ConcreteAdapter(FrameworkAdapter):
    """Minimal concrete implementation for testing the base class."""

    def get_framework_name(self) -> str:
        return "test-framework"

    def wrap(self, agent_or_callable: object) -> object:
        return agent_or_callable

    def emit_events(self, bus: EventBus) -> None:
        self._bus = bus


class TestFrameworkAdapterBase:
    def test_agent_id_property(self) -> None:
        bus = EventBus()
        adapter = ConcreteAdapter("my-agent", bus)
        assert adapter.agent_id == "my-agent"

    def test_repr_contains_framework_and_agent_id(self) -> None:
        bus = EventBus()
        adapter = ConcreteAdapter("my-agent", bus)
        text = repr(adapter)
        assert "test-framework" in text
        assert "my-agent" in text

    def test_require_compatible_passes_for_correct_type(self) -> None:
        bus = EventBus()
        adapter = ConcreteAdapter("a", bus)
        # Should not raise
        adapter._require_compatible("hello", str)

    def test_require_compatible_raises_adapter_error_for_wrong_type(self) -> None:
        bus = EventBus()
        adapter = ConcreteAdapter("a", bus)
        with pytest.raises(AdapterError):
            adapter._require_compatible(42, str)

    def test_require_compatible_error_message_contains_framework(self) -> None:
        bus = EventBus()
        adapter = ConcreteAdapter("a", bus)
        with pytest.raises(AdapterError, match="test-framework"):
            adapter._require_compatible([], dict)


# ---------------------------------------------------------------------------
# CallableAdapter
# ---------------------------------------------------------------------------

class TestCallableAdapterSync:
    def test_wrap_sync_returns_coroutine(self) -> None:
        bus = EventBus()
        adapter = CallableAdapter("agent-1", bus)
        wrapped = adapter.wrap(lambda: 42)
        import inspect
        assert inspect.iscoroutinefunction(wrapped)

    async def test_wrap_sync_callable_returns_correct_result(self) -> None:
        bus = EventBus()
        adapter = CallableAdapter("agent-1", bus)
        wrapped = adapter.wrap(lambda x, y: x + y)
        result = await wrapped(3, 4)
        assert result == 7

    async def test_wrap_sync_emits_started_and_stopped_events(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CallableAdapter("agent-1", bus)
        wrapped = adapter.wrap(lambda: "ok")
        await wrapped()
        event_types = [e.event_type for e in events]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.AGENT_STOPPED in event_types

    async def test_wrap_sync_emits_error_event_on_exception(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CallableAdapter("agent-1", bus)

        def failing_fn() -> None:
            raise ValueError("boom")

        wrapped = adapter.wrap(failing_fn)
        with pytest.raises(ValueError, match="boom"):
            await wrapped()

        event_types = [e.event_type for e in events]
        assert EventType.ERROR_OCCURRED in event_types

    def test_wrap_non_callable_raises_adapter_error(self) -> None:
        bus = EventBus()
        adapter = CallableAdapter("agent-1", bus)
        with pytest.raises(AdapterError):
            adapter.wrap("not-a-callable")

    def test_wrap_non_callable_error_message_contains_type(self) -> None:
        bus = EventBus()
        adapter = CallableAdapter("agent-1", bus)
        with pytest.raises(AdapterError, match="str"):
            adapter.wrap("not-a-callable")


class TestCallableAdapterAsync:
    async def test_wrap_async_callable_returns_correct_result(self) -> None:
        bus = EventBus()
        adapter = CallableAdapter("agent-2", bus)

        async def async_double(x: int) -> int:
            return x * 2

        wrapped = adapter.wrap(async_double)
        result = await wrapped(5)
        assert result == 10

    async def test_wrap_async_emits_started_and_stopped_events(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CallableAdapter("agent-2", bus)

        async def async_fn() -> str:
            return "async"

        wrapped = adapter.wrap(async_fn)
        await wrapped()
        event_types = [e.event_type for e in events]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.AGENT_STOPPED in event_types

    async def test_wrap_async_emits_error_event_on_exception(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CallableAdapter("agent-2", bus)

        async def async_fail() -> None:
            raise RuntimeError("async-fail")

        wrapped = adapter.wrap(async_fail)
        with pytest.raises(RuntimeError):
            await wrapped()

        event_types = [e.event_type for e in events]
        assert EventType.ERROR_OCCURRED in event_types

    async def test_emit_events_swaps_bus(self) -> None:
        bus1 = EventBus()
        bus2 = EventBus()
        events_on_bus2 = _collect_events(bus2)
        adapter = CallableAdapter("agent-2", bus1)
        adapter.emit_events(bus2)
        wrapped = adapter.wrap(lambda: None)
        await wrapped()
        assert len(events_on_bus2) >= 2

    def test_get_framework_name(self) -> None:
        bus = EventBus()
        adapter = CallableAdapter("a", bus)
        assert adapter.get_framework_name() == "callable"


# ---------------------------------------------------------------------------
# CrewAIAdapter — crewai not installed (default in test env)
# ---------------------------------------------------------------------------

class TestCrewAIAdapterWithoutCrewAI:
    def test_wrap_returns_original_when_crewai_absent(self) -> None:
        bus = EventBus()
        adapter = CrewAIAdapter("crew-1", bus)

        sentinel = object()
        with patch("agentcore.adapters.crewai._CREWAI_AVAILABLE", False):
            result = adapter.wrap(sentinel)
        assert result is sentinel

    def test_get_framework_name(self) -> None:
        bus = EventBus()
        adapter = CrewAIAdapter("crew-1", bus)
        assert adapter.get_framework_name() == "crewai"

    def test_emit_events_updates_bus(self) -> None:
        bus1 = EventBus()
        bus2 = EventBus()
        adapter = CrewAIAdapter("crew-1", bus1)
        adapter.emit_events(bus2)
        assert adapter._bus is bus2


class TestCrewAIAdapterWithMockCrewAI:
    """Tests exercising the patching logic when crewai is available."""

    def _make_mock_crew(self) -> MagicMock:
        crew = MagicMock()
        crew.kickoff = MagicMock(return_value="result")
        del crew.kickoff_async  # ensure it doesn't have async variant by default
        return crew

    def test_wrap_patches_kickoff_and_emits_started_stopped(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CrewAIAdapter("crew-1", bus)

        crew = self._make_mock_crew()
        with patch("agentcore.adapters.crewai._CREWAI_AVAILABLE", True):
            result_crew = adapter.wrap(crew)

        result_crew.kickoff()
        event_types = [e.event_type for e in events]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.AGENT_STOPPED in event_types

    def test_wrap_kickoff_propagates_exception_and_emits_error(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CrewAIAdapter("crew-1", bus)

        crew = self._make_mock_crew()
        crew.kickoff.side_effect = RuntimeError("kickoff-failed")

        with patch("agentcore.adapters.crewai._CREWAI_AVAILABLE", True):
            result_crew = adapter.wrap(crew)

        with pytest.raises(RuntimeError, match="kickoff-failed"):
            result_crew.kickoff()

        event_types = [e.event_type for e in events]
        assert EventType.ERROR_OCCURRED in event_types

    def test_wrap_patches_kickoff_async_when_present(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CrewAIAdapter("crew-1", bus)

        crew = MagicMock()
        crew.kickoff = MagicMock(return_value="sync-result")

        async def async_kickoff(*args: object, **kwargs: object) -> str:
            return "async-result"

        crew.kickoff_async = async_kickoff

        with patch("agentcore.adapters.crewai._CREWAI_AVAILABLE", True):
            result_crew = adapter.wrap(crew)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(result_crew.kickoff_async())
        finally:
            loop.close()
        assert result == "async-result"
        event_types = [e.event_type for e in events]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.AGENT_STOPPED in event_types

    def test_wrap_kickoff_async_propagates_exception_and_emits_error(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = CrewAIAdapter("crew-1", bus)

        crew = MagicMock()
        crew.kickoff = MagicMock(return_value="ok")

        async def async_kickoff_fail(*args: object, **kwargs: object) -> None:
            raise ValueError("async-boom")

        crew.kickoff_async = async_kickoff_fail

        with patch("agentcore.adapters.crewai._CREWAI_AVAILABLE", True):
            result_crew = adapter.wrap(crew)

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(ValueError, match="async-boom"):
                loop.run_until_complete(result_crew.kickoff_async())
        finally:
            loop.close()

        event_types = [e.event_type for e in events]
        assert EventType.ERROR_OCCURRED in event_types


# ---------------------------------------------------------------------------
# LangChainAdapter — langchain not installed path
# ---------------------------------------------------------------------------

class TestLangChainAdapterWithoutLangChain:
    def test_wrap_returns_original_when_langchain_absent(self) -> None:
        bus = EventBus()
        adapter = LangChainAdapter("lc-1", bus)
        sentinel = object()
        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", False):
            result = adapter.wrap(sentinel)
        assert result is sentinel

    def test_get_framework_name(self) -> None:
        bus = EventBus()
        adapter = LangChainAdapter("lc-1", bus)
        assert adapter.get_framework_name() == "langchain"

    def test_emit_events_updates_bus_and_handler(self) -> None:
        bus1 = EventBus()
        bus2 = EventBus()
        adapter = LangChainAdapter("lc-1", bus1)
        # Force a handler to exist
        handler = _AgentCoreCallbackHandler("lc-1", bus1)
        adapter._handler = handler
        adapter.emit_events(bus2)
        assert adapter._bus is bus2
        assert handler._bus is bus2

    def test_emit_events_without_handler_is_safe(self) -> None:
        bus1 = EventBus()
        bus2 = EventBus()
        adapter = LangChainAdapter("lc-1", bus1)
        # _handler is None by default
        adapter.emit_events(bus2)  # must not raise
        assert adapter._bus is bus2


class TestLangChainAdapterWithMockLangChain:
    """Tests that exercise the langchain-present code paths via mocking."""

    def _make_handler(self) -> _AgentCoreCallbackHandler:
        bus = EventBus()
        return _AgentCoreCallbackHandler("agent-lc", bus)

    def test_wrap_with_config_uses_with_config(self) -> None:
        bus = EventBus()
        adapter = LangChainAdapter("lc-1", bus)

        runnable = MagicMock()
        configured = MagicMock()
        runnable.with_config.return_value = configured

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            result = adapter.wrap(runnable)

        assert result is configured
        runnable.with_config.assert_called_once()

    def test_wrap_with_callbacks_appends_handler(self) -> None:
        bus = EventBus()
        adapter = LangChainAdapter("lc-1", bus)

        chain = MagicMock(spec=[])  # no with_config
        chain.callbacks = []

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            result = adapter.wrap(chain)

        assert result is chain
        assert len(chain.callbacks) == 1

    def test_wrap_raises_adapter_error_for_incompatible_object(self) -> None:
        bus = EventBus()
        adapter = LangChainAdapter("lc-1", bus)

        class Incompatible:
            pass

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            with pytest.raises(AdapterError):
                adapter.wrap(Incompatible())

    def test_callback_handler_on_chain_start_emits_started(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_chain_start({"name": "chain"}, {"input": "x"}, run_id=uuid4())

        assert any(e.event_type == EventType.AGENT_STARTED for e in events)

    def test_callback_handler_on_chain_end_emits_stopped(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_chain_end({"output": "y"}, run_id=uuid4())

        assert any(e.event_type == EventType.AGENT_STOPPED for e in events)

    def test_callback_handler_on_chain_error_emits_error_occurred(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_chain_error(ValueError("chain-err"), run_id=uuid4())

        assert any(e.event_type == EventType.ERROR_OCCURRED for e in events)

    def test_callback_handler_on_tool_start_emits_tool_called(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_tool_start({"name": "my_tool"}, "input str", run_id=uuid4())

        assert any(e.event_type == EventType.TOOL_CALLED for e in events)

    def test_callback_handler_on_tool_end_emits_tool_completed(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_tool_end("output", run_id=uuid4())

        assert any(e.event_type == EventType.TOOL_COMPLETED for e in events)

    def test_callback_handler_on_tool_error_emits_tool_failed(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_tool_error(RuntimeError("tool-err"), run_id=uuid4())

        assert any(e.event_type == EventType.TOOL_FAILED for e in events)

    def test_callback_handler_on_llm_end_emits_cost_incurred(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        mock_response = MagicMock()
        mock_response.llm_output = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_llm_end(mock_response, run_id=uuid4())

        assert any(e.event_type == EventType.COST_INCURRED for e in events)

    def test_callback_handler_on_llm_end_without_token_usage(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        mock_response = MagicMock()
        mock_response.llm_output = {}

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_llm_end(mock_response, run_id=uuid4())

        # Should still emit COST_INCURRED, just without token data
        assert any(e.event_type == EventType.COST_INCURRED for e in events)

    def test_callback_handler_on_llm_end_without_llm_output(self) -> None:
        """Handler should tolerate a response with no llm_output attribute."""
        bus = EventBus()
        events = _collect_events(bus)
        handler = _AgentCoreCallbackHandler("agent-lc", bus)

        class MinimalResponse:
            pass

        with patch("agentcore.adapters.langchain._LANGCHAIN_AVAILABLE", True):
            handler.on_llm_end(MinimalResponse(), run_id=uuid4())

        assert any(e.event_type == EventType.COST_INCURRED for e in events)
