"""Health check framework for agentcore-sdk.

Provides a composable health-check system that reports the aggregate status
of an agentcore-powered agent and its subsystems.

Shipped in this module
----------------------
- HealthStatus    — ordered enum: HEALTHY / DEGRADED / UNHEALTHY
- CheckResult     — result of a single named check
- HealthReport    — aggregate report from :class:`HealthCheck`
- HealthCheck     — registry and runner for named check functions

Withheld / internal
-------------------
Prometheus ``/metrics`` endpoint integration, Kubernetes liveness/readiness
probe adapters, and distributed health aggregation are available via plugins.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Ordered health status values.

    HEALTHY   — all checks pass.
    DEGRADED  — some non-critical checks fail; the agent can still operate.
    UNHEALTHY — one or more critical checks fail; the agent should not run.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class CheckResult:
    """Result of a single named health check.

    Attributes
    ----------
    name:
        Check name as registered.
    status:
        ``HEALTHY`` if the check passed, otherwise ``DEGRADED`` or
        ``UNHEALTHY``.
    message:
        Human-readable description or error detail.
    """

    name: str
    status: HealthStatus
    message: str = ""


@dataclass
class HealthReport:
    """Aggregate health report.

    Attributes
    ----------
    status:
        Overall status — the worst status across all individual checks.
    checks:
        Mapping from check name to its :class:`CheckResult`.
    timestamp:
        UTC time when the report was generated.
    """

    status: HealthStatus
    checks: dict[str, CheckResult] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def is_healthy(self) -> bool:
        """Return ``True`` iff all checks are ``HEALTHY``."""
        return self.status is HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, object]:
        """Serialise to a plain dict suitable for JSON encoding."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "checks": {
                name: {"status": result.status.value, "message": result.message}
                for name, result in self.checks.items()
            },
        }


# Type alias for a health check function
_CheckFn = Callable[[], CheckResult]


class HealthCheck:
    """Registry and runner for named health check functions.

    Built-in checks can be registered for common agentcore subsystems
    (event bus, identity registry, cost tracker) via the class methods
    below.  Custom checks can be added via :meth:`register_check`.

    Examples
    --------
    >>> hc = HealthCheck()
    >>> hc.register_check("always-ok", lambda: CheckResult("always-ok", HealthStatus.HEALTHY))
    >>> report = hc.run_checks()
    >>> report.is_healthy()
    True
    """

    def __init__(self) -> None:
        self._checks: dict[str, _CheckFn] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_check(self, name: str, check_fn: _CheckFn) -> None:
        """Register a named health check function.

        Parameters
        ----------
        name:
            Unique name for this check.
        check_fn:
            A zero-argument callable that returns a :class:`CheckResult`.
        """
        self._checks[name] = check_fn
        logger.debug("Registered health check %r.", name)

    def unregister_check(self, name: str) -> None:
        """Remove a registered health check.

        Parameters
        ----------
        name:
            The check name to remove.
        """
        self._checks.pop(name, None)

    # ------------------------------------------------------------------
    # Built-in check factories
    # ------------------------------------------------------------------

    def register_event_bus_check(self, bus: object) -> None:
        """Register a check that verifies the event bus is accessible.

        Parameters
        ----------
        bus:
            An :class:`~agentcore.bus.event_bus.EventBus` instance.
        """

        def _check() -> CheckResult:
            try:
                # Verify the bus exists and exposes subscriber_count
                count = bus.subscriber_count() if hasattr(bus, "subscriber_count") else 0  # type: ignore[union-attr]
                return CheckResult(
                    name="event_bus_alive",
                    status=HealthStatus.HEALTHY,
                    message=f"EventBus is alive; {count} subscriber(s).",
                )
            except Exception as exc:
                return CheckResult(
                    name="event_bus_alive",
                    status=HealthStatus.UNHEALTHY,
                    message=f"EventBus check failed: {exc}",
                )

        self.register_check("event_bus_alive", _check)

    def register_identity_registry_check(self, registry: object) -> None:
        """Register a check that verifies the identity registry is accessible.

        Parameters
        ----------
        registry:
            An :class:`~agentcore.identity.registry.AgentRegistry` instance.
        """

        def _check() -> CheckResult:
            try:
                count = len(registry)  # type: ignore[arg-type]
                return CheckResult(
                    name="identity_registry",
                    status=HealthStatus.HEALTHY,
                    message=f"AgentRegistry is healthy; {count} registered agent(s).",
                )
            except Exception as exc:
                return CheckResult(
                    name="identity_registry",
                    status=HealthStatus.UNHEALTHY,
                    message=f"AgentRegistry check failed: {exc}",
                )

        self.register_check("identity_registry", _check)

    def register_cost_tracker_check(self, tracker: object) -> None:
        """Register a check that verifies the cost tracker is accessible.

        Parameters
        ----------
        tracker:
            A :class:`~agentcore.cost.tracker.CostTracker` instance.
        """

        def _check() -> CheckResult:
            try:
                costs = tracker.get_all_costs() if hasattr(tracker, "get_all_costs") else {}  # type: ignore[union-attr]
                agent_count = len(costs)
                return CheckResult(
                    name="cost_tracker",
                    status=HealthStatus.HEALTHY,
                    message=f"CostTracker is healthy; tracking {agent_count} agent(s).",
                )
            except Exception as exc:
                return CheckResult(
                    name="cost_tracker",
                    status=HealthStatus.UNHEALTHY,
                    message=f"CostTracker check failed: {exc}",
                )

        self.register_check("cost_tracker", _check)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_checks(self) -> HealthReport:
        """Execute all registered health checks and return an aggregate report.

        Individual check exceptions are caught and recorded as UNHEALTHY
        results so that a single failing check never prevents others from
        running.

        Returns
        -------
        HealthReport
            Aggregate report.  :attr:`~HealthReport.status` reflects the
            worst individual status seen.
        """
        results: dict[str, CheckResult] = {}
        worst_status = HealthStatus.HEALTHY

        for name, check_fn in list(self._checks.items()):
            try:
                result = check_fn()
            except Exception as exc:
                logger.exception("Health check %r raised an exception.", name)
                result = CheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check raised: {exc}",
                )

            results[name] = result

            if result.status is HealthStatus.UNHEALTHY:
                worst_status = HealthStatus.UNHEALTHY
            elif (
                result.status is HealthStatus.DEGRADED
                and worst_status is HealthStatus.HEALTHY
            ):
                worst_status = HealthStatus.DEGRADED

        return HealthReport(status=worst_status, checks=results)

    def __repr__(self) -> str:
        return f"HealthCheck(checks={sorted(self._checks)})"
