"""Plugin capability contract system.

Plugins declare what capabilities they *provide* and what they *require*.
The :class:`CapabilityRegistry` validates that all required capabilities are
satisfied before any plugin is activated.

This prevents partial-activation bugs where a plugin starts but fails at
runtime because a dependency is missing.

Example
-------
::

    registry = CapabilityRegistry()
    registry.register(
        PluginContract(
            plugin_id="memory_plugin",
            provides={"memory.store", "memory.retrieve"},
            requires={"config.loader"},
        )
    )
    registry.register(
        PluginContract(
            plugin_id="config_plugin",
            provides={"config.loader"},
            requires=set(),
        )
    )
    report = registry.validate()
    assert report.all_satisfied
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PluginContract:
    """Typed capability contract for a plugin.

    Attributes
    ----------
    plugin_id:
        Unique identifier for the plugin.
    provides:
        Set of capability tokens this plugin offers.
    requires:
        Set of capability tokens this plugin needs from others.
    version:
        Semantic version string of the plugin.
    optional_requires:
        Capabilities that enhance the plugin but are not mandatory.
    """

    plugin_id: str
    provides: frozenset[str]
    requires: frozenset[str]
    version: str = "1.0.0"
    optional_requires: frozenset[str] = field(default_factory=frozenset)

    def __init__(
        self,
        plugin_id: str,
        provides: set[str] | frozenset[str],
        requires: set[str] | frozenset[str],
        version: str = "1.0.0",
        optional_requires: set[str] | frozenset[str] | None = None,
    ) -> None:
        # Use object.__setattr__ because the dataclass is frozen
        object.__setattr__(self, "plugin_id", plugin_id)
        object.__setattr__(self, "provides", frozenset(provides))
        object.__setattr__(self, "requires", frozenset(requires))
        object.__setattr__(self, "version", version)
        object.__setattr__(
            self,
            "optional_requires",
            frozenset(optional_requires) if optional_requires else frozenset(),
        )


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationReport:
    """Result of validating all plugin contracts in the registry.

    Attributes
    ----------
    all_satisfied:
        True when every required capability is provided by some plugin.
    unsatisfied_requirements:
        Mapping of plugin_id → set of unmet capability tokens.
    satisfied_requirements:
        Mapping of plugin_id → set of met capability tokens.
    available_capabilities:
        Union of all capabilities provided by registered plugins.
    """

    all_satisfied: bool
    unsatisfied_requirements: dict[str, set[str]]
    satisfied_requirements: dict[str, set[str]]
    available_capabilities: frozenset[str]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class CapabilityValidationError(Exception):
    """Raised when required capabilities cannot be satisfied.

    Attributes
    ----------
    report:
        The :class:`ValidationReport` describing what is missing.
    """

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        missing = {
            plugin: sorted(caps)
            for plugin, caps in report.unsatisfied_requirements.items()
            if caps
        }
        super().__init__(f"Unsatisfied capability requirements: {missing}")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class CapabilityRegistry:
    """Register plugins and validate their capability contracts.

    The registry accumulates :class:`PluginContract` declarations and
    can validate that every ``requires`` declaration is satisfied by
    some other registered plugin's ``provides``.

    Example
    -------
    ::

        registry = CapabilityRegistry()
        registry.register(
            PluginContract("plugin_a", provides={"cap.x"}, requires=set())
        )
        registry.register(
            PluginContract("plugin_b", provides={"cap.y"}, requires={"cap.x"})
        )
        report = registry.validate()
        assert report.all_satisfied
    """

    def __init__(self) -> None:
        self._contracts: dict[str, PluginContract] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, contract: PluginContract) -> None:
        """Register a plugin contract.

        Parameters
        ----------
        contract:
            The :class:`PluginContract` to register.

        Raises
        ------
        ValueError
            If a contract with the same ``plugin_id`` is already registered.
        """
        if contract.plugin_id in self._contracts:
            raise ValueError(
                f"Plugin '{contract.plugin_id}' is already registered"
            )
        self._contracts[contract.plugin_id] = contract

    def unregister(self, plugin_id: str) -> bool:
        """Remove a plugin contract from the registry.

        Parameters
        ----------
        plugin_id:
            The plugin to remove.

        Returns
        -------
        bool
            True if the plugin was found and removed.
        """
        if plugin_id in self._contracts:
            del self._contracts[plugin_id]
            return True
        return False

    def get_contract(self, plugin_id: str) -> PluginContract | None:
        """Return the contract for *plugin_id*, or None if not registered.

        Parameters
        ----------
        plugin_id:
            Plugin to look up.

        Returns
        -------
        PluginContract | None
        """
        return self._contracts.get(plugin_id)

    def registered_plugins(self) -> list[str]:
        """Return IDs of all registered plugins.

        Returns
        -------
        list[str]
            Sorted list of plugin IDs.
        """
        return sorted(self._contracts.keys())

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> ValidationReport:
        """Validate that all required capabilities are satisfied.

        Collects the union of all provided capabilities, then checks each
        plugin's requirements against that pool.

        Returns
        -------
        ValidationReport
            Full report of satisfied and unsatisfied requirements.
        """
        all_provided: frozenset[str] = frozenset(
            cap
            for contract in self._contracts.values()
            for cap in contract.provides
        )

        unsatisfied: dict[str, set[str]] = {}
        satisfied: dict[str, set[str]] = {}

        for plugin_id, contract in self._contracts.items():
            missing: set[str] = set()
            met: set[str] = set()
            for required_cap in contract.requires:
                if required_cap in all_provided:
                    met.add(required_cap)
                else:
                    missing.add(required_cap)
            unsatisfied[plugin_id] = missing
            satisfied[plugin_id] = met

        all_satisfied = all(len(v) == 0 for v in unsatisfied.values())

        return ValidationReport(
            all_satisfied=all_satisfied,
            unsatisfied_requirements=unsatisfied,
            satisfied_requirements=satisfied,
            available_capabilities=all_provided,
        )

    def activate_all(self) -> ValidationReport:
        """Validate all contracts and raise if any requirements are unmet.

        Returns
        -------
        ValidationReport
            The validation report (if all satisfied).

        Raises
        ------
        CapabilityValidationError
            If one or more required capabilities are not provided.
        """
        report = self.validate()
        if not report.all_satisfied:
            raise CapabilityValidationError(report)
        return report

    def available_capabilities(self) -> frozenset[str]:
        """Return the union of all capabilities provided by registered plugins.

        Returns
        -------
        frozenset[str]
            All available capability tokens.
        """
        return frozenset(
            cap
            for contract in self._contracts.values()
            for cap in contract.provides
        )

    def find_providers(self, capability: str) -> list[str]:
        """Return IDs of plugins that provide *capability*.

        Parameters
        ----------
        capability:
            The capability token to search for.

        Returns
        -------
        list[str]
            Plugin IDs that declare this capability in their ``provides``.
        """
        return [
            plugin_id
            for plugin_id, contract in self._contracts.items()
            if capability in contract.provides
        ]

    def __len__(self) -> int:
        """Return the number of registered plugins."""
        return len(self._contracts)


__all__ = [
    "CapabilityRegistry",
    "CapabilityValidationError",
    "PluginContract",
    "ValidationReport",
]
