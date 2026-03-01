#!/usr/bin/env python3
"""Example: Cost Tracking

Demonstrates the CostTracker, BudgetManager, and MODEL_PRICING table
to monitor and control LLM spend.

Usage:
    python examples/04_cost_tracking.py

Requirements:
    pip install agentcore-sdk
"""
from __future__ import annotations

from agentcore import (
    CostTracker,
    TokenUsage,
    AgentCosts,
    BasicBudgetManager,
    MODEL_PRICING,
    get_pricing,
)


def simulate_llm_calls(tracker: CostTracker) -> None:
    """Simulate multiple LLM calls with token tracking."""
    calls: list[tuple[str, int, int]] = [
        ("claude-haiku-4", 500, 200),
        ("claude-haiku-4", 1200, 400),
        ("claude-sonnet-4", 800, 600),
        ("gpt-4o-mini", 300, 150),
        ("claude-haiku-4", 2000, 800),
    ]
    for model, input_tokens, output_tokens in calls:
        usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        tracker.record(model=model, usage=usage)


def main() -> None:
    # Step 1: Show available model pricing
    print("Available model pricing (first 5):")
    for model, pricing in list(MODEL_PRICING.items())[:5]:
        print(f"  [{model}] in=${pricing.input_per_token:.8f} out=${pricing.output_per_token:.8f}")

    # Step 2: Create a cost tracker
    tracker = CostTracker(agent_id="demo-agent")

    # Step 3: Simulate LLM calls
    simulate_llm_calls(tracker)

    # Step 4: Get cost summary
    costs: AgentCosts = tracker.get_costs()
    print(f"\nCost summary for '{costs.agent_id}':")
    print(f"  Total cost: ${costs.total_cost_usd:.6f}")
    print(f"  Total calls: {costs.total_calls}")
    print(f"  Total input tokens: {costs.total_input_tokens:,}")
    print(f"  Total output tokens: {costs.total_output_tokens:,}")

    # Step 5: Per-model breakdown
    print("\nPer-model breakdown:")
    for model, model_costs in costs.by_model.items():
        print(f"  [{model}] ${model_costs.total_cost_usd:.6f} "
              f"| {model_costs.call_count} calls "
              f"| {model_costs.total_input_tokens:,} in / {model_costs.total_output_tokens:,} out")

    # Step 6: Budget management
    budget_manager = BasicBudgetManager(daily_limit_usd=0.50)
    remaining = budget_manager.remaining(costs.total_cost_usd)
    utilisation = budget_manager.utilisation(costs.total_cost_usd)
    print(f"\nBudget status:")
    print(f"  Limit: ${budget_manager.daily_limit_usd:.2f}")
    print(f"  Spent: ${costs.total_cost_usd:.6f}")
    print(f"  Remaining: ${remaining:.6f}")
    print(f"  Utilisation: {utilisation * 100:.1f}%")
    print(f"  Exceeded: {budget_manager.is_exceeded(costs.total_cost_usd)}")


if __name__ == "__main__":
    main()
