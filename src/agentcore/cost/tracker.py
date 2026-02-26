"""Token cost tracker for agentcore-sdk.

Accumulates token usage and computes USD costs per agent, rolling up to
global totals on demand.  Thread-safe for concurrent agent workloads.

Shipped in this module
----------------------
- TokenUsage    — named tuple for a single record
- AgentCosts    — aggregated cost summary for an agent
- CostTracker   — thread-safe cost accumulator

Withheld / internal
-------------------
Cost-anomaly detection, multi-currency conversion, invoice generation,
and per-project budget roll-ups are available via plugins.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import NamedTuple

from agentcore.cost.pricing import get_pricing
from agentcore.schema.errors import CostTrackingError


class TokenUsage(NamedTuple):
    """A single token-usage record.

    Attributes
    ----------
    model:
        The model that was called.
    input_tokens:
        Number of input (prompt) tokens consumed.
    output_tokens:
        Number of output (completion) tokens generated.
    cost_usd:
        Computed USD cost for this call.
    """

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class AgentCosts:
    """Aggregated cost data for a single agent.

    Attributes
    ----------
    agent_id:
        The agent this summary belongs to.
    total_cost_usd:
        Sum of all recorded call costs.
    total_input_tokens:
        Total input tokens across all calls.
    total_output_tokens:
        Total output tokens across all calls.
    records:
        Individual usage records in recording order.
    """

    agent_id: str
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    records: list[TokenUsage] = field(default_factory=list)


class CostTracker:
    """Thread-safe accumulator for token costs across agents and models.

    Examples
    --------
    >>> tracker = CostTracker()
    >>> cost = tracker.record("agent-1", "gpt-4o", 500, 200)
    >>> tracker.get_total("agent-1") > 0
    True
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._costs: dict[str, AgentCosts] = {}

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        agent_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record a token usage event and return the computed USD cost.

        If pricing data for *model* is unavailable, the cost is recorded as
        ``0.0`` and a ``CostTrackingError`` is raised.

        Parameters
        ----------
        agent_id:
            The agent that made the call.
        model:
            The model identifier (e.g. ``"claude-sonnet-4-5"``).
        input_tokens:
            Number of input tokens.
        output_tokens:
            Number of output tokens.

        Returns
        -------
        float
            Computed USD cost for this call.

        Raises
        ------
        CostTrackingError
            If the model has no pricing entry in the catalogue.
        """
        pricing = get_pricing(model)
        if pricing is None:
            raise CostTrackingError(
                f"No pricing data available for model {model!r}. "
                "Add an entry to MODEL_PRICING or use a known model identifier.",
                context={"agent_id": agent_id, "model": model},
            )

        cost_usd = (input_tokens / 1000.0) * pricing.input_cost_per_1k + (
            output_tokens / 1000.0
        ) * pricing.output_cost_per_1k

        usage = TokenUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

        with self._lock:
            if agent_id not in self._costs:
                self._costs[agent_id] = AgentCosts(agent_id=agent_id)
            agent_costs = self._costs[agent_id]
            agent_costs.total_cost_usd += cost_usd
            agent_costs.total_input_tokens += input_tokens
            agent_costs.total_output_tokens += output_tokens
            agent_costs.records.append(usage)

        return cost_usd

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_total(self, agent_id: str) -> float:
        """Return the total USD cost accumulated for *agent_id*.

        Parameters
        ----------
        agent_id:
            The agent to query.

        Returns
        -------
        float
            ``0.0`` if no records exist for this agent.
        """
        with self._lock:
            costs = self._costs.get(agent_id)
        return costs.total_cost_usd if costs is not None else 0.0

    def get_all_costs(self) -> dict[str, AgentCosts]:
        """Return a snapshot of all agent cost summaries.

        Returns
        -------
        dict[str, AgentCosts]
            Keys are agent IDs.  The dict and ``AgentCosts`` objects are
            copies; mutations do not affect the tracker's internal state.
        """
        with self._lock:
            return {
                agent_id: AgentCosts(
                    agent_id=agent_costs.agent_id,
                    total_cost_usd=agent_costs.total_cost_usd,
                    total_input_tokens=agent_costs.total_input_tokens,
                    total_output_tokens=agent_costs.total_output_tokens,
                    records=list(agent_costs.records),
                )
                for agent_id, agent_costs in self._costs.items()
            }

    def get_token_counts(self, agent_id: str) -> tuple[int, int]:
        """Return ``(total_input_tokens, total_output_tokens)`` for *agent_id*.

        Parameters
        ----------
        agent_id:
            The agent to query.

        Returns
        -------
        tuple[int, int]
            ``(0, 0)`` if no records exist.
        """
        with self._lock:
            costs = self._costs.get(agent_id)
        if costs is None:
            return (0, 0)
        return (costs.total_input_tokens, costs.total_output_tokens)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def reset(self, agent_id: str) -> None:
        """Clear all cost records for *agent_id*.

        Parameters
        ----------
        agent_id:
            The agent whose records should be deleted.
        """
        with self._lock:
            self._costs.pop(agent_id, None)

    def reset_all(self) -> None:
        """Clear cost records for all agents."""
        with self._lock:
            self._costs.clear()

    def __repr__(self) -> str:
        with self._lock:
            agents = len(self._costs)
            total = sum(c.total_cost_usd for c in self._costs.values())
        return f"CostTracker(agents={agents}, total_usd={total:.6f})"
