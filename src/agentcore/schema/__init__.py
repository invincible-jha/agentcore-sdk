"""Schema package for agentcore-sdk.

Exports the complete public schema surface: event types, identity, errors,
and the validated configuration model.
"""
from __future__ import annotations

from agentcore.schema.config import AgentConfig
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
from agentcore.schema.events import (
    AgentEvent,
    DecisionEvent,
    EventType,
    ToolCallEvent,
)
from agentcore.schema.identity import AgentIdentity

__all__ = [
    # Events
    "EventType",
    "AgentEvent",
    "ToolCallEvent",
    "DecisionEvent",
    # Identity
    "AgentIdentity",
    # Errors
    "ErrorSeverity",
    "AgentCoreError",
    "ConfigurationError",
    "EventBusError",
    "IdentityError",
    "TelemetryError",
    "CostTrackingError",
    "PluginError",
    "AdapterError",
    # Config
    "AgentConfig",
]
