"""agentcore-sdk — Agent substrate: event schemas, identity, telemetry bridge, plugin registry.

Public API
----------
The stable public surface is everything exported from this module.
Anything inside submodules not re-exported here is considered private
and may change without notice.

Quick-start
-----------
>>> import agentcore
>>> agentcore.__version__
'0.1.0'

>>> from agentcore import EventBus, AgentEvent, EventType
>>> bus = EventBus()
>>> events: list[AgentEvent] = []
>>> bus.subscribe(EventType.AGENT_STARTED, events.append)  # doctest: +ELLIPSIS
'...'
>>> import asyncio
>>> asyncio.run(bus.emit(AgentEvent(EventType.AGENT_STARTED, "agent-1")))
>>> len(events)
1
"""
from __future__ import annotations

__version__: str = "0.1.0"

from agentcore.convenience import AgentCore, Event

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
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
from agentcore.schema.events import AgentEvent, DecisionEvent, EventType, ToolCallEvent
from agentcore.schema.identity import AgentIdentity

# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------
from agentcore.bus.event_bus import EventBus
from agentcore.bus.filters import (
    AgentFilter,
    CompositeFilter,
    EventFilter,
    FilterMode,
    MetadataFilter,
    TypeFilter,
)
from agentcore.bus.subscriber import FilteredSubscriber, Subscriber

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
from agentcore.identity.agent_id import create_identity
from agentcore.identity.provider import BasicIdentityProvider, IdentityProvider
from agentcore.identity.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
from agentcore.telemetry.collector import MetricCollector, MetricSummary
from agentcore.telemetry.exporter import (
    ConsoleExporter,
    JSONFileExporter,
    NullExporter,
    TelemetryExporter,
)
from agentcore.telemetry.otel_bridge import OTelBridge

# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------
from agentcore.cost.budget import BasicBudgetManager, BudgetManager
from agentcore.cost.pricing import MODEL_PRICING, PricingEntry, get_pricing
from agentcore.cost.tracker import AgentCosts, CostTracker, TokenUsage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
from agentcore.config.defaults import DEFAULT_CONFIG
from agentcore.config.loader import ConfigLoader
from agentcore.config.schema import validate_config

# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------
from agentcore.adapters.base import FrameworkAdapter
from agentcore.adapters.callable import CallableAdapter
from agentcore.adapters.crewai import CrewAIAdapter
from agentcore.adapters.langchain import LangChainAdapter

# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------
from agentcore.plugins.loader import PluginLoader
from agentcore.plugins.registry import (
    AgentPlugin,
    AgentPluginRegistry,
    PluginAlreadyRegisteredError,
    PluginNotFoundError,
    PluginRegistry,
)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
from agentcore.health.check import CheckResult, HealthCheck, HealthReport, HealthStatus

__all__ = [
    "__version__",
    "AgentCore",
    "Event",
    # schema — events
    "EventType",
    "AgentEvent",
    "ToolCallEvent",
    "DecisionEvent",
    # schema — identity
    "AgentIdentity",
    # schema — errors
    "ErrorSeverity",
    "AgentCoreError",
    "ConfigurationError",
    "EventBusError",
    "IdentityError",
    "TelemetryError",
    "CostTrackingError",
    "PluginError",
    "AdapterError",
    # schema — config
    "AgentConfig",
    # bus
    "EventBus",
    "Subscriber",
    "FilteredSubscriber",
    "EventFilter",
    "FilterMode",
    "TypeFilter",
    "AgentFilter",
    "MetadataFilter",
    "CompositeFilter",
    # identity
    "create_identity",
    "AgentRegistry",
    "IdentityProvider",
    "BasicIdentityProvider",
    # telemetry
    "MetricCollector",
    "MetricSummary",
    "TelemetryExporter",
    "ConsoleExporter",
    "JSONFileExporter",
    "NullExporter",
    "OTelBridge",
    # cost
    "CostTracker",
    "TokenUsage",
    "AgentCosts",
    "MODEL_PRICING",
    "PricingEntry",
    "get_pricing",
    "BudgetManager",
    "BasicBudgetManager",
    # config
    "DEFAULT_CONFIG",
    "ConfigLoader",
    "validate_config",
    # adapters
    "FrameworkAdapter",
    "CallableAdapter",
    "LangChainAdapter",
    "CrewAIAdapter",
    # plugins
    "PluginRegistry",
    "AgentPlugin",
    "AgentPluginRegistry",
    "PluginLoader",
    "PluginNotFoundError",
    "PluginAlreadyRegisteredError",
    # health
    "HealthStatus",
    "CheckResult",
    "HealthReport",
    "HealthCheck",
]
