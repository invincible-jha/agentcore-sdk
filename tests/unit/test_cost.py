"""Unit tests for agentcore.cost — pricing, tracker, and budget."""
from __future__ import annotations

import threading

import pytest

from agentcore.cost.budget import BasicBudgetManager
from agentcore.cost.pricing import MODEL_PRICING, PricingEntry, get_pricing
from agentcore.cost.tracker import AgentCosts, CostTracker, TokenUsage
from agentcore.schema.errors import CostTrackingError


# ---------------------------------------------------------------------------
# PricingEntry
# ---------------------------------------------------------------------------

class TestPricingEntry:
    def test_pricing_entry_is_named_tuple(self) -> None:
        entry = PricingEntry(input_cost_per_1k=0.01, output_cost_per_1k=0.03)
        assert entry.input_cost_per_1k == 0.01
        assert entry.output_cost_per_1k == 0.03

    def test_model_pricing_contains_known_models(self) -> None:
        assert "gpt-4o" in MODEL_PRICING
        assert "claude-opus-4" in MODEL_PRICING


# ---------------------------------------------------------------------------
# get_pricing
# ---------------------------------------------------------------------------

class TestGetPricing:
    def test_exact_match_known_model(self) -> None:
        entry = get_pricing("gpt-4o")
        assert entry is not None
        assert entry.input_cost_per_1k == 0.005

    def test_case_insensitive_match(self) -> None:
        entry = get_pricing("GPT-4O")
        assert entry is not None

    def test_prefix_fuzzy_match(self) -> None:
        # "claude-opus" should resolve to "claude-opus-4"
        entry = get_pricing("claude-opus")
        assert entry is not None

    def test_unknown_model_returns_none(self) -> None:
        result = get_pricing("totally-unknown-model-xyz-9999")
        assert result is None

    def test_all_catalogue_entries_are_reachable(self) -> None:
        for model_id in MODEL_PRICING:
            assert get_pricing(model_id) is not None


# ---------------------------------------------------------------------------
# CostTracker
# ---------------------------------------------------------------------------

class TestCostTracker:
    def test_record_known_model_returns_positive_cost(self) -> None:
        tracker = CostTracker()
        cost = tracker.record("agent-1", "gpt-4o", input_tokens=1000, output_tokens=500)
        assert cost > 0

    def test_record_unknown_model_raises_cost_tracking_error(self) -> None:
        tracker = CostTracker()
        with pytest.raises(CostTrackingError):
            tracker.record("agent-1", "model-does-not-exist", 100, 50)

    def test_get_total_returns_zero_for_unknown_agent(self) -> None:
        tracker = CostTracker()
        assert tracker.get_total("nonexistent-agent") == 0.0

    def test_get_total_accumulates_multiple_records(self) -> None:
        tracker = CostTracker()
        cost1 = tracker.record("agent-1", "gpt-4o", 500, 200)
        cost2 = tracker.record("agent-1", "gpt-4o", 300, 100)
        assert tracker.get_total("agent-1") == pytest.approx(cost1 + cost2)

    def test_get_all_costs_returns_copy(self) -> None:
        tracker = CostTracker()
        tracker.record("agent-1", "gpt-4o", 100, 50)
        all_costs = tracker.get_all_costs()
        assert "agent-1" in all_costs
        assert isinstance(all_costs["agent-1"], AgentCosts)
        # Mutating the copy must not affect tracker state
        del all_costs["agent-1"]
        assert tracker.get_total("agent-1") > 0

    def test_get_token_counts_returns_zeros_for_unknown_agent(self) -> None:
        tracker = CostTracker()
        assert tracker.get_token_counts("nobody") == (0, 0)

    def test_get_token_counts_accumulates(self) -> None:
        tracker = CostTracker()
        tracker.record("agent-1", "gpt-4o", 300, 100)
        tracker.record("agent-1", "gpt-4o", 200, 50)
        inp, out = tracker.get_token_counts("agent-1")
        assert inp == 500
        assert out == 150

    def test_reset_clears_single_agent(self) -> None:
        tracker = CostTracker()
        tracker.record("agent-1", "gpt-4o", 100, 50)
        tracker.record("agent-2", "gpt-4o", 100, 50)
        tracker.reset("agent-1")
        assert tracker.get_total("agent-1") == 0.0
        assert tracker.get_total("agent-2") > 0

    def test_reset_nonexistent_agent_is_safe(self) -> None:
        tracker = CostTracker()
        tracker.reset("ghost-agent")  # must not raise

    def test_reset_all_clears_everything(self) -> None:
        tracker = CostTracker()
        tracker.record("a", "gpt-4o", 100, 50)
        tracker.record("b", "gpt-4o", 100, 50)
        tracker.reset_all()
        assert tracker.get_all_costs() == {}

    def test_repr_contains_agent_count_and_total(self) -> None:
        tracker = CostTracker()
        tracker.record("a", "gpt-4o", 1000, 500)
        text = repr(tracker)
        assert "agents=1" in text
        assert "total_usd=" in text

    def test_thread_safe_concurrent_recording(self) -> None:
        tracker = CostTracker()
        errors: list[Exception] = []

        def record_many() -> None:
            try:
                for _ in range(50):
                    tracker.record("shared-agent", "gpt-4o", 10, 5)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=record_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        inp, out = tracker.get_token_counts("shared-agent")
        assert inp == 50 * 5 * 10
        assert out == 50 * 5 * 5


# ---------------------------------------------------------------------------
# BasicBudgetManager
# ---------------------------------------------------------------------------

class TestBasicBudgetManager:
    def test_set_budget_and_check_returns_full_budget_before_spend(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("agent-1", 10.00)
        assert manager.check_budget("agent-1") == pytest.approx(10.00)

    def test_record_spend_deducts_from_budget(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("agent-1", 10.00)
        manager.record_spend("agent-1", 3.50)
        assert manager.check_budget("agent-1") == pytest.approx(6.50)

    def test_is_over_budget_false_when_within_limit(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("agent-1", 5.00)
        manager.record_spend("agent-1", 4.99)
        assert manager.is_over_budget("agent-1") is False

    def test_is_over_budget_true_when_exceeded(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("agent-1", 5.00)
        manager.record_spend("agent-1", 5.01)
        assert manager.is_over_budget("agent-1") is True

    def test_is_over_budget_false_when_no_budget_set(self) -> None:
        manager = BasicBudgetManager()
        assert manager.is_over_budget("nobody") is False

    def test_check_budget_raises_when_no_budget_set(self) -> None:
        manager = BasicBudgetManager()
        with pytest.raises(CostTrackingError):
            manager.check_budget("no-budget-agent")

    def test_set_budget_negative_raises_cost_tracking_error(self) -> None:
        manager = BasicBudgetManager()
        with pytest.raises(CostTrackingError):
            manager.set_budget("agent-1", -1.0)

    def test_set_budget_zero_is_valid(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("agent-1", 0.0)
        assert manager.check_budget("agent-1") == 0.0

    def test_set_budget_preserves_existing_spend(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("agent-1", 10.00)
        manager.record_spend("agent-1", 3.00)
        # Increase the budget mid-run
        manager.set_budget("agent-1", 20.00)
        # Spent amount must still be 3.00
        assert manager.check_budget("agent-1") == pytest.approx(17.00)

    def test_record_spend_for_unknown_agent_is_silently_ignored(self) -> None:
        manager = BasicBudgetManager()
        manager.record_spend("ghost-agent", 99.99)  # must not raise

    def test_get_all_budgets_returns_snapshot(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("a", 5.00)
        manager.record_spend("a", 2.00)
        all_budgets = manager.get_all_budgets()
        assert "a" in all_budgets
        assert all_budgets["a"]["budget"] == pytest.approx(5.00)
        assert all_budgets["a"]["spent"] == pytest.approx(2.00)
        assert all_budgets["a"]["remaining"] == pytest.approx(3.00)

    def test_get_all_budgets_empty(self) -> None:
        manager = BasicBudgetManager()
        assert manager.get_all_budgets() == {}

    def test_repr_shows_agent_count(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("x", 1.00)
        assert "1" in repr(manager)

    def test_thread_safe_concurrent_spend(self) -> None:
        manager = BasicBudgetManager()
        manager.set_budget("shared", 1_000_000.00)
        errors: list[Exception] = []

        def spend_many() -> None:
            try:
                for _ in range(100):
                    manager.record_spend("shared", 1.00)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=spend_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        remaining = manager.check_budget("shared")
        assert remaining == pytest.approx(1_000_000.00 - 500.00)
