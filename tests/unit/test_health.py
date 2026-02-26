"""Unit tests for agentcore.health.check."""
from __future__ import annotations

import pytest

from agentcore.health.check import (
    CheckResult,
    HealthCheck,
    HealthReport,
    HealthStatus,
)


# ---------------------------------------------------------------------------
# HealthStatus
# ---------------------------------------------------------------------------

class TestHealthStatus:
    def test_values(self) -> None:
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


# ---------------------------------------------------------------------------
# CheckResult
# ---------------------------------------------------------------------------

class TestCheckResult:
    def test_defaults(self) -> None:
        result = CheckResult(name="test", status=HealthStatus.HEALTHY)
        assert result.message == ""

    def test_custom_message(self) -> None:
        result = CheckResult(name="db", status=HealthStatus.UNHEALTHY, message="timeout")
        assert result.message == "timeout"


# ---------------------------------------------------------------------------
# HealthReport
# ---------------------------------------------------------------------------

class TestHealthReport:
    def test_is_healthy_true_when_healthy_status(self) -> None:
        report = HealthReport(status=HealthStatus.HEALTHY)
        assert report.is_healthy() is True

    def test_is_healthy_false_when_degraded(self) -> None:
        report = HealthReport(status=HealthStatus.DEGRADED)
        assert report.is_healthy() is False

    def test_is_healthy_false_when_unhealthy(self) -> None:
        report = HealthReport(status=HealthStatus.UNHEALTHY)
        assert report.is_healthy() is False

    def test_to_dict_contains_status_and_timestamp(self) -> None:
        report = HealthReport(status=HealthStatus.HEALTHY)
        data = report.to_dict()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "checks" in data

    def test_to_dict_includes_check_details(self) -> None:
        check = CheckResult(name="c1", status=HealthStatus.DEGRADED, message="slow")
        report = HealthReport(status=HealthStatus.DEGRADED, checks={"c1": check})
        data = report.to_dict()
        assert "c1" in data["checks"]
        assert data["checks"]["c1"]["status"] == "degraded"


# ---------------------------------------------------------------------------
# HealthCheck — registration
# ---------------------------------------------------------------------------

class TestHealthCheckRegistration:
    def test_register_and_run_passing_check(self) -> None:
        hc = HealthCheck()
        hc.register_check(
            "always-ok",
            lambda: CheckResult("always-ok", HealthStatus.HEALTHY),
        )
        report = hc.run_checks()
        assert report.is_healthy()
        assert "always-ok" in report.checks

    def test_register_multiple_checks(self) -> None:
        hc = HealthCheck()
        hc.register_check("c1", lambda: CheckResult("c1", HealthStatus.HEALTHY))
        hc.register_check("c2", lambda: CheckResult("c2", HealthStatus.HEALTHY))
        report = hc.run_checks()
        assert set(report.checks.keys()) == {"c1", "c2"}

    def test_unregister_check_removes_it(self) -> None:
        hc = HealthCheck()
        hc.register_check("c1", lambda: CheckResult("c1", HealthStatus.HEALTHY))
        hc.unregister_check("c1")
        report = hc.run_checks()
        assert "c1" not in report.checks

    def test_unregister_nonexistent_check_is_safe(self) -> None:
        hc = HealthCheck()
        hc.unregister_check("ghost")  # must not raise

    def test_repr_contains_check_names(self) -> None:
        hc = HealthCheck()
        hc.register_check("my-check", lambda: CheckResult("my-check", HealthStatus.HEALTHY))
        assert "my-check" in repr(hc)


# ---------------------------------------------------------------------------
# HealthCheck — run_checks aggregation
# ---------------------------------------------------------------------------

class TestHealthCheckRunChecks:
    def test_no_checks_returns_healthy(self) -> None:
        hc = HealthCheck()
        report = hc.run_checks()
        assert report.is_healthy()

    def test_one_unhealthy_check_makes_report_unhealthy(self) -> None:
        hc = HealthCheck()
        hc.register_check(
            "bad", lambda: CheckResult("bad", HealthStatus.UNHEALTHY, "down")
        )
        report = hc.run_checks()
        assert report.status is HealthStatus.UNHEALTHY

    def test_one_degraded_check_makes_report_degraded(self) -> None:
        hc = HealthCheck()
        hc.register_check(
            "slow", lambda: CheckResult("slow", HealthStatus.DEGRADED, "latency")
        )
        report = hc.run_checks()
        assert report.status is HealthStatus.DEGRADED

    def test_unhealthy_beats_degraded(self) -> None:
        hc = HealthCheck()
        hc.register_check("a", lambda: CheckResult("a", HealthStatus.DEGRADED))
        hc.register_check("b", lambda: CheckResult("b", HealthStatus.UNHEALTHY))
        report = hc.run_checks()
        assert report.status is HealthStatus.UNHEALTHY

    def test_check_that_raises_is_recorded_as_unhealthy(self) -> None:
        hc = HealthCheck()

        def exploding_check() -> CheckResult:
            raise RuntimeError("explode")

        hc.register_check("exploding", exploding_check)
        report = hc.run_checks()
        assert report.status is HealthStatus.UNHEALTHY
        assert "exploding" in report.checks
        assert "explode" in report.checks["exploding"].message

    def test_one_failing_check_does_not_prevent_others(self) -> None:
        hc = HealthCheck()
        hc.register_check("fail", lambda: (_ for _ in ()).throw(RuntimeError("x")))  # type: ignore[arg-type]
        hc.register_check("ok", lambda: CheckResult("ok", HealthStatus.HEALTHY))
        report = hc.run_checks()
        assert "ok" in report.checks


# ---------------------------------------------------------------------------
# HealthCheck — built-in check factories
# ---------------------------------------------------------------------------

class TestHealthCheckBuiltinFactories:
    def test_register_event_bus_check_healthy(self) -> None:
        hc = HealthCheck()

        class FakeBus:
            def subscriber_count(self) -> int:
                return 3

        hc.register_event_bus_check(FakeBus())
        report = hc.run_checks()
        assert report.checks["event_bus_alive"].status is HealthStatus.HEALTHY
        assert "3" in report.checks["event_bus_alive"].message

    def test_register_event_bus_check_without_subscriber_count_attribute(self) -> None:
        hc = HealthCheck()

        class MinimalBus:
            pass

        hc.register_event_bus_check(MinimalBus())
        report = hc.run_checks()
        assert report.checks["event_bus_alive"].status is HealthStatus.HEALTHY

    def test_register_event_bus_check_unhealthy_when_raises(self) -> None:
        hc = HealthCheck()

        class BrokenBus:
            def subscriber_count(self) -> int:
                raise ConnectionError("no connection")

        hc.register_event_bus_check(BrokenBus())
        report = hc.run_checks()
        assert report.checks["event_bus_alive"].status is HealthStatus.UNHEALTHY

    def test_register_identity_registry_check_healthy(self) -> None:
        hc = HealthCheck()

        class FakeRegistry:
            def __len__(self) -> int:
                return 2

        hc.register_identity_registry_check(FakeRegistry())
        report = hc.run_checks()
        assert report.checks["identity_registry"].status is HealthStatus.HEALTHY

    def test_register_identity_registry_check_unhealthy_when_raises(self) -> None:
        hc = HealthCheck()

        class BrokenRegistry:
            def __len__(self) -> int:
                raise RuntimeError("broken")

        hc.register_identity_registry_check(BrokenRegistry())
        report = hc.run_checks()
        assert report.checks["identity_registry"].status is HealthStatus.UNHEALTHY

    def test_register_cost_tracker_check_healthy(self) -> None:
        hc = HealthCheck()

        class FakeTracker:
            def get_all_costs(self) -> dict[str, object]:
                return {"agent-1": object()}

        hc.register_cost_tracker_check(FakeTracker())
        report = hc.run_checks()
        assert report.checks["cost_tracker"].status is HealthStatus.HEALTHY

    def test_register_cost_tracker_check_without_get_all_costs(self) -> None:
        hc = HealthCheck()

        class MinimalTracker:
            pass

        hc.register_cost_tracker_check(MinimalTracker())
        report = hc.run_checks()
        assert report.checks["cost_tracker"].status is HealthStatus.HEALTHY

    def test_register_cost_tracker_check_unhealthy_when_raises(self) -> None:
        hc = HealthCheck()

        class BrokenTracker:
            def get_all_costs(self) -> dict[str, object]:
                raise IOError("disk full")

        hc.register_cost_tracker_check(BrokenTracker())
        report = hc.run_checks()
        assert report.checks["cost_tracker"].status is HealthStatus.UNHEALTHY
