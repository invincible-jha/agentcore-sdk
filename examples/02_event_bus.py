#!/usr/bin/env python3
"""Example: Event Bus

Demonstrates the EventBus with filters, typed subscriptions, and
priority-based delivery across multiple subscribers.

Usage:
    python examples/02_event_bus.py

Requirements:
    pip install agentcore-sdk
"""
from __future__ import annotations

import asyncio

from agentcore import (
    AgentEvent,
    DecisionEvent,
    EventBus,
    EventType,
    FilterMode,
    ToolCallEvent,
    TypeFilter,
    AgentFilter,
)


async def main_async() -> None:
    # Step 1: Create event bus
    bus = EventBus()

    # Step 2: Collect events in typed lists
    all_events: list[AgentEvent] = []
    tool_events: list[ToolCallEvent] = []
    decision_events: list[DecisionEvent] = []

    # Step 3: Subscribe with type filters
    bus.subscribe(EventType.AGENT_STARTED, all_events.append)
    bus.subscribe(EventType.AGENT_COMPLETED, all_events.append)
    bus.subscribe(EventType.TOOL_CALLED, lambda e: tool_events.append(e))  # type: ignore[arg-type]
    bus.subscribe(EventType.DECISION_MADE, lambda e: decision_events.append(e))  # type: ignore[arg-type]

    # Subscribe only to events from a specific agent
    agent_filter = AgentFilter(agent_ids=["agent-alpha"])
    alpha_events: list[AgentEvent] = []

    def handle_alpha(event: AgentEvent) -> None:
        if agent_filter.matches(event):
            alpha_events.append(event)

    bus.subscribe(EventType.AGENT_STARTED, handle_alpha)
    bus.subscribe(EventType.AGENT_COMPLETED, handle_alpha)

    # Step 4: Emit various events
    agents = ["agent-alpha", "agent-beta", "agent-gamma"]
    for agent_id in agents:
        await bus.emit(AgentEvent(EventType.AGENT_STARTED, agent_id))

    await bus.emit(ToolCallEvent(
        tool_name="search_db",
        tool_args={"query": "annual revenue"},
        source_agent_id="agent-alpha",
    ))

    await bus.emit(DecisionEvent(
        decision="use_vector_search",
        rationale="Query is semantic in nature",
        source_agent_id="agent-alpha",
        confidence=0.88,
    ))

    for agent_id in agents:
        await bus.emit(AgentEvent(EventType.AGENT_COMPLETED, agent_id))

    # Step 5: Report results
    print(f"Total lifecycle events: {len(all_events)}")
    print(f"Tool call events: {len(tool_events)}")
    print(f"Decision events: {len(decision_events)}")
    print(f"Alpha-only events: {len(alpha_events)}")

    for event in tool_events:
        print(f"  Tool call: {event.tool_name}({event.tool_args})")

    for event in decision_events:
        print(f"  Decision: '{event.decision}' confidence={event.confidence:.2f}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
