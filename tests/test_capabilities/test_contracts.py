"""Tests for agentcore.capabilities.contracts."""
from __future__ import annotations

import pytest

from agentcore.capabilities.contracts import (
    CapabilityRegistry,
    CapabilityValidationError,
    PluginContract,
    ValidationReport,
)


# ---------------------------------------------------------------------------
# PluginContract
# ---------------------------------------------------------------------------


class TestPluginContract:
    def test_provides_is_frozenset(self) -> None:
        contract = PluginContract("p1", provides={"cap.a"}, requires=set())
        assert isinstance(contract.provides, frozenset)

    def test_requires_is_frozenset(self) -> None:
        contract = PluginContract("p1", provides=set(), requires={"cap.b"})
        assert isinstance(contract.requires, frozenset)

    def test_frozen_immutable(self) -> None:
        contract = PluginContract("p1", provides={"cap.a"}, requires=set())
        with pytest.raises((AttributeError, TypeError)):
            contract.plugin_id = "other"  # type: ignore[misc]

    def test_default_version(self) -> None:
        contract = PluginContract("p1", provides=set(), requires=set())
        assert contract.version == "1.0.0"

    def test_custom_version(self) -> None:
        contract = PluginContract("p1", provides=set(), requires=set(), version="2.1.0")
        assert contract.version == "2.1.0"

    def test_optional_requires_defaults_empty(self) -> None:
        contract = PluginContract("p1", provides=set(), requires=set())
        assert contract.optional_requires == frozenset()

    def test_optional_requires_set(self) -> None:
        contract = PluginContract(
            "p1",
            provides=set(),
            requires=set(),
            optional_requires={"cap.opt"},
        )
        assert "cap.opt" in contract.optional_requires


# ---------------------------------------------------------------------------
# CapabilityRegistry — registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_single_plugin(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides={"cap.x"}, requires=set()))
        assert len(registry) == 1

    def test_registered_plugins_sorted(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("b_plugin", provides=set(), requires=set()))
        registry.register(PluginContract("a_plugin", provides=set(), requires=set()))
        assert registry.registered_plugins() == ["a_plugin", "b_plugin"]

    def test_duplicate_registration_raises(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides=set(), requires=set()))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(PluginContract("p1", provides=set(), requires=set()))

    def test_unregister_existing_returns_true(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides=set(), requires=set()))
        assert registry.unregister("p1") is True
        assert len(registry) == 0

    def test_unregister_nonexistent_returns_false(self) -> None:
        registry = CapabilityRegistry()
        assert registry.unregister("nobody") is False

    def test_get_contract_returns_contract(self) -> None:
        registry = CapabilityRegistry()
        contract = PluginContract("p1", provides={"cap.x"}, requires=set())
        registry.register(contract)
        assert registry.get_contract("p1") is contract

    def test_get_contract_missing_returns_none(self) -> None:
        registry = CapabilityRegistry()
        assert registry.get_contract("missing") is None


# ---------------------------------------------------------------------------
# Validation — all satisfied
# ---------------------------------------------------------------------------


class TestValidationSatisfied:
    def test_no_requirements_always_satisfied(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides={"cap.a"}, requires=set()))
        report = registry.validate()
        assert report.all_satisfied is True

    def test_satisfied_single_requirement(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("provider", provides={"cap.x"}, requires=set()))
        registry.register(PluginContract("consumer", provides=set(), requires={"cap.x"}))
        report = registry.validate()
        assert report.all_satisfied is True

    def test_self_satisfying_chain(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides={"cap.a"}, requires=set()))
        registry.register(PluginContract("p2", provides={"cap.b"}, requires={"cap.a"}))
        registry.register(PluginContract("p3", provides=set(), requires={"cap.b"}))
        report = registry.validate()
        assert report.all_satisfied is True

    def test_satisfied_requirements_populated(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides={"cap.x"}, requires=set()))
        registry.register(PluginContract("p2", provides=set(), requires={"cap.x"}))
        report = registry.validate()
        assert "cap.x" in report.satisfied_requirements["p2"]


# ---------------------------------------------------------------------------
# Validation — unsatisfied
# ---------------------------------------------------------------------------


class TestValidationUnsatisfied:
    def test_missing_requirement_not_satisfied(self) -> None:
        registry = CapabilityRegistry()
        registry.register(
            PluginContract("consumer", provides=set(), requires={"cap.missing"})
        )
        report = registry.validate()
        assert report.all_satisfied is False

    def test_unsatisfied_requirements_populated(self) -> None:
        registry = CapabilityRegistry()
        registry.register(
            PluginContract("p1", provides=set(), requires={"cap.x", "cap.y"})
        )
        report = registry.validate()
        assert "cap.x" in report.unsatisfied_requirements["p1"]

    def test_partial_satisfaction(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("provider", provides={"cap.a"}, requires=set()))
        registry.register(
            PluginContract("consumer", provides=set(), requires={"cap.a", "cap.missing"})
        )
        report = registry.validate()
        assert report.all_satisfied is False
        assert "cap.a" in report.satisfied_requirements["consumer"]
        assert "cap.missing" in report.unsatisfied_requirements["consumer"]


# ---------------------------------------------------------------------------
# activate_all
# ---------------------------------------------------------------------------


class TestActivateAll:
    def test_activate_all_satisfied_returns_report(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides={"x"}, requires=set()))
        report = registry.activate_all()
        assert isinstance(report, ValidationReport)

    def test_activate_all_unsatisfied_raises(self) -> None:
        registry = CapabilityRegistry()
        registry.register(
            PluginContract("p1", provides=set(), requires={"missing.cap"})
        )
        with pytest.raises(CapabilityValidationError) as exc_info:
            registry.activate_all()
        assert exc_info.value.report.all_satisfied is False


# ---------------------------------------------------------------------------
# Available capabilities and find_providers
# ---------------------------------------------------------------------------


class TestAvailabilityHelpers:
    def test_available_capabilities_union(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides={"cap.a", "cap.b"}, requires=set()))
        registry.register(PluginContract("p2", provides={"cap.c"}, requires=set()))
        caps = registry.available_capabilities()
        assert caps == frozenset({"cap.a", "cap.b", "cap.c"})

    def test_find_providers_returns_plugin_ids(self) -> None:
        registry = CapabilityRegistry()
        registry.register(PluginContract("p1", provides={"shared.cap"}, requires=set()))
        registry.register(PluginContract("p2", provides={"shared.cap"}, requires=set()))
        providers = registry.find_providers("shared.cap")
        assert set(providers) == {"p1", "p2"}

    def test_find_providers_empty_for_unknown(self) -> None:
        registry = CapabilityRegistry()
        assert registry.find_providers("nonexistent") == []

    def test_empty_registry_no_capabilities(self) -> None:
        registry = CapabilityRegistry()
        assert registry.available_capabilities() == frozenset()
