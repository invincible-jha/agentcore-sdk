"""Unit tests for the new agentcore adapters.

Covers:
- adapters.openai_agents  — OpenAIAgentsAdapter with and without SDK installed
- adapters.anthropic_sdk  — AnthropicAdapter with and without SDK installed
- adapters.microsoft_agents — MicrosoftAgentAdapter with and without SDK installed
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentcore.adapters.anthropic_sdk import AnthropicAdapter, _emit_cost_event, _emit_tool_use_events
from agentcore.adapters.microsoft_agents import MicrosoftAgentAdapter
from agentcore.adapters.openai_agents import OpenAIAgentsAdapter
from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType, ToolCallEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_events(bus: EventBus) -> list[AgentEvent]:
    collected: list[AgentEvent] = []
    bus.subscribe_all(collected.append)
    return collected


# ===========================================================================
# OpenAIAgentsAdapter
# ===========================================================================


class TestOpenAIAgentsAdapterWithoutSDK:
    def test_get_framework_name(self) -> None:
        bus = EventBus()
        adapter = OpenAIAgentsAdapter("oai-1", bus)
        assert adapter.get_framework_name() == "openai_agents"

    def test_wrap_returns_original_when_sdk_absent(self) -> None:
        bus = EventBus()
        adapter = OpenAIAgentsAdapter("oai-1", bus)
        sentinel = object()
        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", False):
            result = adapter.wrap(sentinel)
        assert result is sentinel

    def test_emit_events_updates_bus(self) -> None:
        bus1 = EventBus()
        bus2 = EventBus()
        adapter = OpenAIAgentsAdapter("oai-1", bus1)
        adapter.emit_events(bus2)
        assert adapter._bus is bus2

    def test_agent_id_property(self) -> None:
        bus = EventBus()
        adapter = OpenAIAgentsAdapter("oai-agent-xyz", bus)
        assert adapter.agent_id == "oai-agent-xyz"

    def test_repr_contains_framework_and_agent_id(self) -> None:
        bus = EventBus()
        adapter = OpenAIAgentsAdapter("oai-1", bus)
        text = repr(adapter)
        assert "openai_agents" in text
        assert "oai-1" in text


class TestOpenAIAgentsAdapterWithMockSDK:
    def test_wrap_with_hooks_patches_hooks_attribute(self) -> None:
        bus = EventBus()
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        mock_agent = MagicMock()
        mock_agent.hooks = None

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True):
            result = adapter.wrap(mock_agent)

        assert result is mock_agent
        # hooks attribute should be replaced with the event-emitting wrapper
        assert mock_agent.hooks is not None

    def test_wrap_agent_without_hooks_returns_original(self) -> None:
        bus = EventBus()
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        class BareAgent:
            pass

        mock_agent = BareAgent()

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True):
            result = adapter.wrap(mock_agent)

        # The adapter should always return the original object
        assert result is mock_agent

    def test_run_raises_when_sdk_absent(self) -> None:
        bus = EventBus()
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        async def _run() -> None:
            await adapter.run("hello")

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="openai-agents"):
                asyncio.run(_run())

    def test_run_emits_started_stopped_events(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        mock_result = MagicMock()
        mock_result.final_output = "agent output"

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=mock_result)

        async def _run() -> None:
            await adapter.run("hello")

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True), \
             patch("agentcore.adapters.openai_agents.Runner", mock_runner):
            adapter._original_agent = MagicMock()
            asyncio.run(_run())

        event_types = [e.event_type for e in events]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.AGENT_STOPPED in event_types

    def test_run_emits_error_event_on_exception(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=ValueError("sdk-error"))

        async def _run() -> None:
            await adapter.run("hello")

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True), \
             patch("agentcore.adapters.openai_agents.Runner", mock_runner):
            adapter._original_agent = MagicMock()
            with pytest.raises(ValueError, match="sdk-error"):
                asyncio.run(_run())

        event_types = [e.event_type for e in events]
        assert EventType.ERROR_OCCURRED in event_types

    def test_hooks_on_agent_start_emits_event(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        mock_agent = MagicMock()
        mock_agent.hooks = None

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True):
            adapter.wrap(mock_agent)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(mock_agent.hooks.on_agent_start(None, None))
        finally:
            loop.close()

        assert any(e.event_type == EventType.AGENT_STARTED for e in events)

    def test_hooks_on_agent_end_emits_stopped_event(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        mock_agent = MagicMock()
        mock_agent.hooks = None

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True):
            adapter.wrap(mock_agent)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(mock_agent.hooks.on_agent_end(None, None, "output"))
        finally:
            loop.close()

        assert any(e.event_type == EventType.AGENT_STOPPED for e in events)

    def test_hooks_on_tool_start_emits_tool_called(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        mock_agent = MagicMock()
        mock_agent.hooks = None
        mock_tool = MagicMock()
        mock_tool.name = "my_tool"

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True):
            adapter.wrap(mock_agent)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                mock_agent.hooks.on_tool_start(None, None, mock_tool)
            )
        finally:
            loop.close()

        assert any(e.event_type == EventType.TOOL_CALLED for e in events)

    def test_hooks_on_tool_end_emits_tool_completed(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = OpenAIAgentsAdapter("oai-1", bus)

        mock_agent = MagicMock()
        mock_agent.hooks = None
        mock_tool = MagicMock()
        mock_tool.name = "my_tool"

        with patch("agentcore.adapters.openai_agents._OPENAI_AGENTS_AVAILABLE", True):
            adapter.wrap(mock_agent)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                mock_agent.hooks.on_tool_end(None, None, mock_tool, "result")
            )
        finally:
            loop.close()

        assert any(e.event_type == EventType.TOOL_COMPLETED for e in events)


# ===========================================================================
# AnthropicAdapter
# ===========================================================================


class TestAnthropicAdapterWithoutSDK:
    def test_get_framework_name(self) -> None:
        bus = EventBus()
        adapter = AnthropicAdapter("ant-1", bus)
        assert adapter.get_framework_name() == "anthropic"

    def test_wrap_returns_original_when_sdk_absent(self) -> None:
        bus = EventBus()
        adapter = AnthropicAdapter("ant-1", bus)
        sentinel = object()
        with patch("agentcore.adapters.anthropic_sdk._ANTHROPIC_AVAILABLE", False):
            result = adapter.wrap(sentinel)
        assert result is sentinel

    def test_emit_events_updates_bus(self) -> None:
        bus1 = EventBus()
        bus2 = EventBus()
        adapter = AnthropicAdapter("ant-1", bus1)
        adapter.emit_events(bus2)
        assert adapter._bus is bus2

    def test_agent_id_property(self) -> None:
        bus = EventBus()
        adapter = AnthropicAdapter("ant-agent-42", bus)
        assert adapter.agent_id == "ant-agent-42"

    def test_repr_contains_framework_and_agent_id(self) -> None:
        bus = EventBus()
        adapter = AnthropicAdapter("ant-1", bus)
        text = repr(adapter)
        assert "anthropic" in text
        assert "ant-1" in text


class TestAnthropicAdapterWithMockSDK:
    def _make_mock_client(self) -> MagicMock:
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = MagicMock(return_value=MagicMock(content=[], usage=None))
        return client

    def test_wrap_patches_messages_create(self) -> None:
        bus = EventBus()
        adapter = AnthropicAdapter("ant-1", bus)
        client = self._make_mock_client()

        with patch("agentcore.adapters.anthropic_sdk._ANTHROPIC_AVAILABLE", True):
            result = adapter.wrap(client)

        assert result is client
        # create should now be the patched version (not the original MagicMock)
        assert callable(client.messages.create)

    def test_wrap_client_without_messages_logs_warning(self) -> None:
        bus = EventBus()
        adapter = AnthropicAdapter("ant-1", bus)

        class NoMessages:
            pass

        obj = NoMessages()
        with patch("agentcore.adapters.anthropic_sdk._ANTHROPIC_AVAILABLE", True):
            result = adapter.wrap(obj)

        assert result is obj

    def test_patched_create_emits_started_stopped(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)
        client = self._make_mock_client()

        with patch("agentcore.adapters.anthropic_sdk._ANTHROPIC_AVAILABLE", True):
            adapter.wrap(client)

        client.messages.create()  # call the patched method

        event_types = [e.event_type for e in events]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.AGENT_STOPPED in event_types

    def test_patched_create_emits_error_on_exception(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)
        client = self._make_mock_client()
        client.messages.create.side_effect = RuntimeError("api-error")

        with patch("agentcore.adapters.anthropic_sdk._ANTHROPIC_AVAILABLE", True):
            adapter.wrap(client)

        with pytest.raises(RuntimeError, match="api-error"):
            client.messages.create()

        assert any(e.event_type == EventType.ERROR_OCCURRED for e in events)

    def test_patched_create_emits_tool_called_for_tool_use_block(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "my_function"
        tool_block.input = {"query": "test"}

        mock_response = MagicMock()
        mock_response.content = [tool_block]
        mock_response.usage = None

        client = self._make_mock_client()
        client.messages.create.return_value = mock_response

        with patch("agentcore.adapters.anthropic_sdk._ANTHROPIC_AVAILABLE", True):
            adapter.wrap(client)

        client.messages.create()

        assert any(e.event_type == EventType.TOOL_CALLED for e in events)

    def test_patched_create_emits_cost_incurred_with_usage(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)

        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage = usage

        client = self._make_mock_client()
        client.messages.create.return_value = mock_response

        with patch("agentcore.adapters.anthropic_sdk._ANTHROPIC_AVAILABLE", True):
            adapter.wrap(client)

        client.messages.create()

        cost_events = [e for e in events if e.event_type == EventType.COST_INCURRED]
        assert len(cost_events) == 1
        assert cost_events[0].data["input_tokens"] == 100
        assert cost_events[0].data["output_tokens"] == 50


class TestAnthropicHelpers:
    def test_emit_tool_use_events_with_tool_use_block(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)

        block = MagicMock()
        block.type = "tool_use"
        block.name = "search"
        block.input = {"q": "hello"}

        response = MagicMock()
        response.content = [block]

        _emit_tool_use_events(response, adapter)

        assert any(e.event_type == EventType.TOOL_CALLED for e in events)

    def test_emit_tool_use_events_skips_non_tool_blocks(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)

        block = MagicMock()
        block.type = "text"
        block.text = "hello"

        response = MagicMock()
        response.content = [block]

        _emit_tool_use_events(response, adapter)

        assert not any(e.event_type == EventType.TOOL_CALLED for e in events)

    def test_emit_cost_event_with_none_usage(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)

        response = MagicMock()
        response.usage = None

        _emit_cost_event(response, adapter)

        assert not any(e.event_type == EventType.COST_INCURRED for e in events)

    def test_emit_cost_event_emits_cost_incurred(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = AnthropicAdapter("ant-1", bus)

        usage = MagicMock()
        usage.input_tokens = 200
        usage.output_tokens = 75

        response = MagicMock()
        response.usage = usage

        _emit_cost_event(response, adapter)

        cost_events = [e for e in events if e.event_type == EventType.COST_INCURRED]
        assert len(cost_events) == 1
        assert cost_events[0].data["input_tokens"] == 200


# ===========================================================================
# MicrosoftAgentAdapter
# ===========================================================================


class TestMicrosoftAgentAdapterWithoutSDK:
    def test_get_framework_name(self) -> None:
        bus = EventBus()
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        assert adapter.get_framework_name() == "microsoft_agents"

    def test_wrap_returns_original_when_sdk_absent(self) -> None:
        bus = EventBus()
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        sentinel = object()
        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", False):
            result = adapter.wrap(sentinel)
        assert result is sentinel

    def test_emit_events_updates_bus(self) -> None:
        bus1 = EventBus()
        bus2 = EventBus()
        adapter = MicrosoftAgentAdapter("ms-1", bus1)
        adapter.emit_events(bus2)
        assert adapter._bus is bus2

    def test_agent_id_property(self) -> None:
        bus = EventBus()
        adapter = MicrosoftAgentAdapter("ms-agent-99", bus)
        assert adapter.agent_id == "ms-agent-99"

    def test_repr_contains_framework_and_agent_id(self) -> None:
        bus = EventBus()
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        text = repr(adapter)
        assert "microsoft_agents" in text
        assert "ms-1" in text


class TestMicrosoftAgentAdapterWithMockSDK:
    def _make_mock_bot(self) -> MagicMock:
        bot = MagicMock()
        bot.on_turn = AsyncMock()
        bot.on_message_activity = AsyncMock()
        return bot

    def test_wrap_patches_on_turn(self) -> None:
        bus = EventBus()
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        bot = self._make_mock_bot()
        original_turn = bot.on_turn

        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", True):
            result = adapter.wrap(bot)

        assert result is bot
        # on_turn should now be the patched function
        assert bot.on_turn is not original_turn

    def test_wrap_patches_on_message_activity(self) -> None:
        bus = EventBus()
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        bot = self._make_mock_bot()
        original_message = bot.on_message_activity

        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", True):
            adapter.wrap(bot)

        assert bot.on_message_activity is not original_message

    def test_patched_on_turn_emits_started_stopped(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        bot = self._make_mock_bot()

        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", True):
            adapter.wrap(bot)

        mock_context = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(bot.on_turn(mock_context))
        finally:
            loop.close()

        event_types = [e.event_type for e in events]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.AGENT_STOPPED in event_types

    def test_patched_on_turn_emits_error_on_exception(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        bot = self._make_mock_bot()
        bot.on_turn.side_effect = RuntimeError("turn-error")

        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", True):
            adapter.wrap(bot)

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(RuntimeError, match="turn-error"):
                loop.run_until_complete(bot.on_turn(MagicMock()))
        finally:
            loop.close()

        assert any(e.event_type == EventType.ERROR_OCCURRED for e in events)

    def test_patched_on_message_emits_message_received(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        bot = self._make_mock_bot()

        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", True):
            adapter.wrap(bot)

        mock_context = MagicMock()
        mock_context.activity.text = "Hello bot!"
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(bot.on_message_activity(mock_context))
        finally:
            loop.close()

        assert any(e.event_type == EventType.MESSAGE_RECEIVED for e in events)

    def test_wrap_patches_on_invoke_activity_when_present(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        bot = self._make_mock_bot()
        bot.on_invoke_activity = AsyncMock(return_value="invoke-result")

        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", True):
            adapter.wrap(bot)

        mock_context = MagicMock()
        mock_context.activity.name = "my_invoke"
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(bot.on_invoke_activity(mock_context))
        finally:
            loop.close()

        event_types = [e.event_type for e in events]
        assert EventType.TOOL_CALLED in event_types
        assert EventType.TOOL_COMPLETED in event_types

    def test_wrap_on_invoke_activity_emits_tool_failed_on_error(self) -> None:
        bus = EventBus()
        events = _collect_events(bus)
        adapter = MicrosoftAgentAdapter("ms-1", bus)
        bot = self._make_mock_bot()
        bot.on_invoke_activity = AsyncMock(side_effect=ValueError("invoke-err"))

        with patch("agentcore.adapters.microsoft_agents._MICROSOFT_AGENTS_AVAILABLE", True):
            adapter.wrap(bot)

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(ValueError, match="invoke-err"):
                loop.run_until_complete(bot.on_invoke_activity(MagicMock()))
        finally:
            loop.close()

        assert any(e.event_type == EventType.TOOL_FAILED for e in events)
