"""Unit tests for agentcore.schema.errors.

Tests cover the full error hierarchy, severity enum, context payload,
repr formatting, and exception chaining behaviour.
"""
from __future__ import annotations

import pytest

from agentcore.schema.errors import (
    AdapterError,
    AgentCoreError,
    ConfigurationError,
    CostTrackingError,
    ErrorSeverity,
    EventBusError,
    IdentityError,
    PluginError,
    TelemetryError,
)


# ---------------------------------------------------------------------------
# ErrorSeverity enum
# ---------------------------------------------------------------------------


class TestErrorSeverity:
    def test_all_members_are_strings(self) -> None:
        for member in ErrorSeverity:
            assert isinstance(member.value, str)

    def test_expected_members_exist(self) -> None:
        values = {m.value for m in ErrorSeverity}
        assert values == {"critical", "high", "medium", "low", "info"}

    def test_members_are_str_subclass(self) -> None:
        assert isinstance(ErrorSeverity.HIGH, str)
        assert ErrorSeverity.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# AgentCoreError base class
# ---------------------------------------------------------------------------


class TestAgentCoreError:
    def test_message_is_accessible_as_str(self) -> None:
        exc = AgentCoreError("something broke")
        assert str(exc) == "something broke"

    def test_default_severity_is_high(self) -> None:
        exc = AgentCoreError("oops")
        assert exc.severity is ErrorSeverity.HIGH

    def test_custom_severity_stored(self) -> None:
        exc = AgentCoreError("warn", severity=ErrorSeverity.MEDIUM)
        assert exc.severity is ErrorSeverity.MEDIUM

    def test_context_defaults_to_empty_dict(self) -> None:
        exc = AgentCoreError("no context")
        assert exc.context == {}

    def test_context_is_stored_when_provided(self) -> None:
        ctx: dict[str, object] = {"agent_id": "a1", "model": "gpt-4o"}
        exc = AgentCoreError("ctx error", context=ctx)
        assert exc.context == ctx

    def test_none_context_normalised_to_empty_dict(self) -> None:
        exc = AgentCoreError("none ctx", context=None)
        assert exc.context == {}

    def test_repr_contains_class_name(self) -> None:
        exc = AgentCoreError("boom")
        assert "AgentCoreError" in repr(exc)

    def test_repr_contains_severity_value(self) -> None:
        exc = AgentCoreError("boom", severity=ErrorSeverity.LOW)
        assert "low" in repr(exc)

    def test_repr_contains_message(self) -> None:
        exc = AgentCoreError("my error message")
        assert "my error message" in repr(exc)

    def test_is_exception_subclass(self) -> None:
        exc = AgentCoreError("test")
        assert isinstance(exc, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(AgentCoreError) as exc_info:
            raise AgentCoreError("raised", severity=ErrorSeverity.CRITICAL)
        assert exc_info.value.severity is ErrorSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Domain subclasses — inheritance and individuality
# ---------------------------------------------------------------------------


class TestDomainErrorSubclasses:
    @pytest.mark.parametrize(
        "error_cls",
        [
            ConfigurationError,
            EventBusError,
            IdentityError,
            TelemetryError,
            CostTrackingError,
            PluginError,
            AdapterError,
        ],
    )
    def test_is_agentcore_error_subclass(
        self, error_cls: type[AgentCoreError]
    ) -> None:
        exc = error_cls("test msg")
        assert isinstance(exc, AgentCoreError)

    @pytest.mark.parametrize(
        "error_cls",
        [
            ConfigurationError,
            EventBusError,
            IdentityError,
            TelemetryError,
            CostTrackingError,
            PluginError,
            AdapterError,
        ],
    )
    def test_can_be_caught_as_agentcore_error(
        self, error_cls: type[AgentCoreError]
    ) -> None:
        with pytest.raises(AgentCoreError):
            raise error_cls("caught at base")

    @pytest.mark.parametrize(
        "error_cls",
        [
            ConfigurationError,
            EventBusError,
            IdentityError,
            TelemetryError,
            CostTrackingError,
            PluginError,
            AdapterError,
        ],
    )
    def test_severity_and_context_accepted(
        self, error_cls: type[AgentCoreError]
    ) -> None:
        ctx: dict[str, object] = {"key": "val"}
        exc = error_cls("msg", severity=ErrorSeverity.INFO, context=ctx)
        assert exc.severity is ErrorSeverity.INFO
        assert exc.context == ctx

    def test_distinct_domain_errors_are_not_interchangeable(self) -> None:
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("cfg fail")

        # IdentityError should NOT be caught as ConfigurationError
        with pytest.raises(IdentityError):
            raise IdentityError("id fail")
