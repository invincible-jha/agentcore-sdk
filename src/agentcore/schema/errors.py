"""Error taxonomy for agentcore-sdk.

All exceptions raised by agentcore (and by well-behaved plugins) derive from
``AgentCoreError`` so that callers can catch the entire family with a single
``except AgentCoreError`` clause while still being able to distinguish
individual failure modes.

Shipped in this module
----------------------
- ErrorSeverity     — ordered severity enum
- AgentCoreError    — root exception with severity and context payload
- Domain subclasses — ConfigurationError, EventBusError, IdentityError,
                      TelemetryError, CostTrackingError, PluginError,
                      AdapterError

Withheld / internal
-------------------
Structured error reporting pipelines, Sentry integration, and
error-correlation across distributed agents are available via plugins.
"""
from __future__ import annotations

from enum import Enum


class ErrorSeverity(str, Enum):
    """Ordered severity levels for ``AgentCoreError`` instances.

    Severity is purely advisory metadata — it does not change the
    exception-handling semantics, but it lets logging and alerting
    infrastructure filter by impact level.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AgentCoreError(Exception):
    """Root exception for all agentcore failures.

    Parameters
    ----------
    message:
        Human-readable description of what went wrong.
    severity:
        Advisory ``ErrorSeverity`` level.  Defaults to ``HIGH``.
    context:
        Optional dict of structured metadata (agent IDs, model names, etc.)
        that helps diagnostics without requiring log scraping.

    Examples
    --------
    >>> try:
    ...     raise AgentCoreError("something broke", ErrorSeverity.MEDIUM)
    ... except AgentCoreError as exc:
    ...     print(exc.severity)
    ErrorSeverity.MEDIUM
    """

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.severity: ErrorSeverity = severity
        self.context: dict[str, object] = context or {}

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"message={str(self)!r}, "
            f"severity={self.severity.value!r})"
        )


class ConfigurationError(AgentCoreError):
    """Raised when configuration loading or validation fails.

    Examples: missing required field, unsupported framework name, bad YAML.
    """


class EventBusError(AgentCoreError):
    """Raised for event-bus failures: dead subscribers, full buffers, etc."""


class IdentityError(AgentCoreError):
    """Raised when identity operations fail.

    Examples: duplicate registration, unknown agent ID, verification failure.
    """


class TelemetryError(AgentCoreError):
    """Raised for telemetry / OTel bridge failures."""


class CostTrackingError(AgentCoreError):
    """Raised for cost-tracking and budget-management failures."""


class PluginError(AgentCoreError):
    """Raised when a plugin cannot be loaded, initialised, or shut down."""


class AdapterError(AgentCoreError):
    """Raised when a framework adapter encounters an integration error."""
