"""Budget management for agentcore-sdk.

Provides guard-rails that prevent runaway agents from exceeding spending
limits.  The ``BudgetManager`` is checked by the cost tracker integration
layer before each model call.

Shipped in this module
----------------------
- BudgetManager        — ABC for all budget managers
- BasicBudgetManager   — in-memory implementation for dev / single-process

Extension points
-------------------
Persistent budget storage, cross-tenant budget sharing, proactive
pre-flight cost estimation, and Slack/email budget-alert webhooks are
available via plugins.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from agentcore.schema.errors import CostTrackingError


class BudgetManager(ABC):
    """Abstract base class for per-agent budget management.

    Implementors track budget allocations and spending, exposing helpers
    to check remaining budget and over-budget status.
    """

    @abstractmethod
    def set_budget(self, agent_id: str, budget_usd: float) -> None:
        """Assign a USD spending limit to *agent_id*.

        Parameters
        ----------
        agent_id:
            The agent to budget.
        budget_usd:
            Maximum allowed spend in USD.

        Raises
        ------
        CostTrackingError
            If ``budget_usd`` is negative.
        """

    @abstractmethod
    def check_budget(self, agent_id: str) -> float:
        """Return the remaining USD budget for *agent_id*.

        Parameters
        ----------
        agent_id:
            The agent to query.

        Returns
        -------
        float
            Remaining budget.  May be negative if over-budget.

        Raises
        ------
        CostTrackingError
            If no budget has been set for *agent_id*.
        """

    @abstractmethod
    def record_spend(self, agent_id: str, amount_usd: float) -> None:
        """Deduct *amount_usd* from the *agent_id* budget.

        Parameters
        ----------
        agent_id:
            The spending agent.
        amount_usd:
            Amount to deduct.
        """

    @abstractmethod
    def is_over_budget(self, agent_id: str) -> bool:
        """Return ``True`` if *agent_id* has exceeded its budget.

        Parameters
        ----------
        agent_id:
            The agent to check.

        Returns
        -------
        bool
            ``False`` if no budget is set (permissive default).
        """


class BasicBudgetManager(BudgetManager):
    """Simple in-memory budget manager.

    Thread-safe and suitable for development, testing, and single-process
    deployments.  Spending is tracked independently of the ``CostTracker``
    so that budget checks can be performed pre-flight.

    Examples
    --------
    >>> manager = BasicBudgetManager()
    >>> manager.set_budget("agent-1", 5.00)
    >>> manager.record_spend("agent-1", 2.50)
    >>> manager.check_budget("agent-1")
    2.5
    >>> manager.is_over_budget("agent-1")
    False
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Maps agent_id -> (budget_usd, spent_usd)
        self._budgets: dict[str, tuple[float, float]] = {}

    def set_budget(self, agent_id: str, budget_usd: float) -> None:
        """Assign or update a budget for *agent_id*.

        If a budget already exists for the agent, its *spent* amount is
        preserved so that mid-run budget adjustments are possible.

        Parameters
        ----------
        agent_id:
            The agent to budget.
        budget_usd:
            Non-negative spending limit in USD.

        Raises
        ------
        CostTrackingError
            If ``budget_usd < 0``.
        """
        if budget_usd < 0:
            raise CostTrackingError(
                f"Budget must be non-negative; got {budget_usd}.",
                context={"agent_id": agent_id, "budget_usd": budget_usd},
            )
        with self._lock:
            existing_spent = self._budgets.get(agent_id, (0.0, 0.0))[1]
            self._budgets[agent_id] = (budget_usd, existing_spent)

    def check_budget(self, agent_id: str) -> float:
        """Return the remaining USD budget for *agent_id*.

        Returns
        -------
        float
            ``budget - spent``.  Negative means over-budget.

        Raises
        ------
        CostTrackingError
            If no budget has been set for *agent_id*.
        """
        with self._lock:
            entry = self._budgets.get(agent_id)
        if entry is None:
            raise CostTrackingError(
                f"No budget set for agent {agent_id!r}. "
                "Call set_budget() first.",
                context={"agent_id": agent_id},
            )
        budget, spent = entry
        return budget - spent

    def record_spend(self, agent_id: str, amount_usd: float) -> None:
        """Deduct *amount_usd* from the agent's budget tracker.

        If no budget has been set, this call is silently ignored (permissive
        mode — callers must call :meth:`set_budget` if they want enforcement).

        Parameters
        ----------
        agent_id:
            The spending agent.
        amount_usd:
            Non-negative USD amount to deduct.
        """
        with self._lock:
            if agent_id not in self._budgets:
                return
            budget, spent = self._budgets[agent_id]
            self._budgets[agent_id] = (budget, spent + amount_usd)

    def is_over_budget(self, agent_id: str) -> bool:
        """Return ``True`` if *agent_id* has exceeded its spending limit.

        Returns ``False`` if no budget has been set (permissive default).

        Parameters
        ----------
        agent_id:
            The agent to check.

        Returns
        -------
        bool
        """
        with self._lock:
            entry = self._budgets.get(agent_id)
        if entry is None:
            return False
        budget, spent = entry
        return spent > budget

    def get_all_budgets(self) -> dict[str, dict[str, float]]:
        """Return a snapshot of all budget entries.

        Returns
        -------
        dict[str, dict[str, float]]
            Maps agent_id -> ``{"budget": float, "spent": float, "remaining": float}``.
        """
        with self._lock:
            snapshot = dict(self._budgets)
        return {
            agent_id: {
                "budget": budget,
                "spent": spent,
                "remaining": budget - spent,
            }
            for agent_id, (budget, spent) in snapshot.items()
        }

    def __repr__(self) -> str:
        with self._lock:
            count = len(self._budgets)
        return f"BasicBudgetManager(agents_with_budget={count})"
