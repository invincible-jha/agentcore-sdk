"""Test that the 3-line quickstart API works for agentcore-sdk."""
from __future__ import annotations


def test_quickstart_import() -> None:
    from agentcore import AgentCore, Event

    core = AgentCore()
    assert core is not None


def test_quickstart_event_creation() -> None:
    from agentcore import Event

    event = Event("agent.started", {"agent_id": "test-agent"})
    assert event is not None
    assert event.event_type == "agent.started"
    assert event.data == {"agent_id": "test-agent"}


def test_quickstart_event_no_data() -> None:
    from agentcore import Event

    event = Event("agent.stopped")
    assert event is not None
    assert event.data == {}


def test_quickstart_core_has_bus() -> None:
    from agentcore import AgentCore
    from agentcore.bus.event_bus import EventBus

    core = AgentCore()
    assert isinstance(core.bus, EventBus)


def test_quickstart_core_has_registry() -> None:
    from agentcore import AgentCore
    from agentcore.identity.registry import AgentRegistry

    core = AgentCore()
    assert isinstance(core.registry, AgentRegistry)


def test_quickstart_repr() -> None:
    from agentcore import AgentCore, Event

    core = AgentCore()
    assert "AgentCore" in repr(core)

    event = Event("agent.started", {"key": "value"})
    assert "Event" in repr(event)
