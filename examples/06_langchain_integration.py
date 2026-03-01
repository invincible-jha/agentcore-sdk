#!/usr/bin/env python3
"""Example: LangChain Integration

Demonstrates using the LangChainAdapter to bridge an agentcore
EventBus into a LangChain callback handler.

Usage:
    python examples/06_langchain_integration.py

Requirements:
    pip install agentcore-sdk langchain langchain-openai
"""
from __future__ import annotations

import asyncio

try:
    from langchain.callbacks.base import BaseCallbackHandler
    from langchain.schema import HumanMessage
    from langchain_openai import ChatOpenAI
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

import agentcore
from agentcore import (
    AgentCore,
    EventType,
    AgentEvent,
    ToolCallEvent,
    CostTracker,
    TokenUsage,
    LangChainAdapter,
)


async def run_with_langchain(core: AgentCore, tracker: CostTracker) -> None:
    """Run a simulated LangChain call through the agentcore adapter."""
    await core.bus.emit(AgentEvent(EventType.AGENT_STARTED, core.agent_id))

    if _LANGCHAIN_AVAILABLE:
        # Real LangChain call
        adapter = LangChainAdapter(bus=core.bus, agent_id=core.agent_id)
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, callbacks=[adapter.as_callback()])
        response = llm.invoke([HumanMessage(content="What is 2+2?")])
        output = response.content
        usage = TokenUsage(input_tokens=10, output_tokens=5)
    else:
        # Stub response
        output = "4"
        usage = TokenUsage(input_tokens=10, output_tokens=5)

    tracker.record(model="gpt-4o-mini", usage=usage)
    await core.bus.emit(AgentEvent(EventType.AGENT_COMPLETED, core.agent_id))
    print(f"  Response: {output}")


async def main_async() -> None:
    print(f"agentcore-sdk version: {agentcore.__version__}")

    if not _LANGCHAIN_AVAILABLE:
        print("LangChain not installed — using stub responses.")
        print("Install with: pip install langchain langchain-openai")

    # Step 1: Create agentcore with cost tracking
    core = AgentCore(agent_id="langchain-agent")
    tracker = CostTracker(agent_id=core.agent_id)

    # Step 2: Subscribe to events for monitoring
    events: list[AgentEvent] = []
    core.bus.subscribe(EventType.AGENT_STARTED, events.append)
    core.bus.subscribe(EventType.AGENT_COMPLETED, events.append)

    # Step 3: Run LangChain calls
    print("\nRunning LangChain calls through agentcore:")
    for _ in range(3):
        await run_with_langchain(core, tracker)

    # Step 4: Report results
    print(f"\nLifecycle events: {len(events)}")
    costs = tracker.get_costs()
    print(f"Total cost: ${costs.total_cost_usd:.6f} | calls={costs.total_calls}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
