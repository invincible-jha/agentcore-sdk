#!/usr/bin/env python3
"""Example: Multi-Agent Coordination

Demonstrates using agentcore's EventBus to coordinate multiple agents
passing tasks and results between each other.

Usage:
    python examples/07_multi_agent.py

Requirements:
    pip install agentcore-sdk
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from agentcore import (
    AgentEvent,
    AgentRegistry,
    AgentConfig,
    EventBus,
    EventType,
    ToolCallEvent,
    DecisionEvent,
    create_identity,
    CostTracker,
    TokenUsage,
)


@dataclass
class AgentTask:
    """A unit of work passed between agents."""
    task_id: str
    description: str
    assigned_to: str
    result: str = ""
    completed: bool = False


class SimpleAgent:
    """Minimal agent that processes tasks and emits events."""

    def __init__(self, agent_id: str, bus: EventBus, tracker: CostTracker) -> None:
        self.agent_id = agent_id
        self._bus = bus
        self._tracker = tracker
        self._completed_tasks: list[str] = []

    async def process(self, task: AgentTask) -> str:
        await self._bus.emit(AgentEvent(EventType.AGENT_STARTED, self.agent_id))
        # Simulate LLM usage
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        self._tracker.record(model="claude-haiku-4", usage=usage)
        # Process the task
        task.result = f"[{self.agent_id}] completed: {task.description[:40]}"
        task.completed = True
        self._completed_tasks.append(task.task_id)
        await self._bus.emit(AgentEvent(EventType.AGENT_COMPLETED, self.agent_id))
        return task.result

    def task_count(self) -> int:
        return len(self._completed_tasks)


async def main_async() -> None:
    # Step 1: Set up shared infrastructure
    bus = EventBus()
    registry = AgentRegistry()
    tracker = CostTracker(agent_id="multi-agent-system")

    # Step 2: Create and register agents
    agent_ids = ["planner", "researcher", "summariser"]
    agents: dict[str, SimpleAgent] = {}

    for agent_id in agent_ids:
        identity = create_identity(agent_id=agent_id)
        config = AgentConfig(
            agent_id=agent_id,
            did=identity.did,
            capabilities=[agent_id],
        )
        registry.register(config)
        agents[agent_id] = SimpleAgent(agent_id=agent_id, bus=bus, tracker=tracker)

    print(f"Multi-agent system: {registry.count()} agents registered")

    # Step 3: Track all lifecycle events
    all_events: list[AgentEvent] = []
    bus.subscribe(EventType.AGENT_STARTED, all_events.append)
    bus.subscribe(EventType.AGENT_COMPLETED, all_events.append)

    # Step 4: Define and execute a pipeline of tasks
    tasks: list[AgentTask] = [
        AgentTask(task_id="t1", description="Plan the research agenda for Q4 AI trends", assigned_to="planner"),
        AgentTask(task_id="t2", description="Research top 5 AI developments in 2025", assigned_to="researcher"),
        AgentTask(task_id="t3", description="Summarise findings into executive brief", assigned_to="summariser"),
    ]

    print("\nExecuting agent pipeline:")
    for task in tasks:
        agent = agents[task.assigned_to]
        result = await agent.process(task)
        print(f"  [{task.assigned_to}] {result}")

    # Step 5: Report results
    print(f"\nPipeline complete:")
    print(f"  Total events: {len(all_events)}")
    print(f"  Agent task counts:")
    for agent_id, agent in agents.items():
        print(f"    {agent_id}: {agent.task_count()} task(s)")

    costs = tracker.get_costs()
    print(f"\nTotal cost: ${costs.total_cost_usd:.6f} | calls={costs.total_calls}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
