#!/usr/bin/env python3
"""Example: Quickstart

Demonstrates the minimal setup for agentcore-sdk using the AgentCore
convenience class and the event bus.

Usage:
    python examples/01_quickstart.py

Requirements:
    pip install agentcore-sdk
"""
from __future__ import annotations

import asyncio

import agentcore
from agentcore import AgentCore, EventType, AgentEvent


async def main_async() -> None:
    print(f"agentcore-sdk version: {agentcore.__version__}")

    # Step 1: Create a zero-config AgentCore instance
    core = AgentCore(agent_id="quickstart-agent")
    print(f"AgentCore created: agent_id={core.agent_id}")

    # Step 2: Subscribe to lifecycle events
    received: list[AgentEvent] = []
    core.bus.subscribe(EventType.AGENT_STARTED, received.append)
    core.bus.subscribe(EventType.AGENT_COMPLETED, received.append)

    # Step 3: Emit lifecycle events
    await core.bus.emit(AgentEvent(EventType.AGENT_STARTED, core.agent_id))
    print("Agent started event emitted.")

    # Simulate work
    response = f"Hello from {core.agent_id}"
    print(f"Agent response: {response}")

    await core.bus.emit(AgentEvent(EventType.AGENT_COMPLETED, core.agent_id))
    print("Agent completed event emitted.")

    # Step 4: Report events received
    print(f"\nLifecycle events received: {len(received)}")
    for event in received:
        print(f"  {event.event_type.value} from {event.source_agent_id}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
