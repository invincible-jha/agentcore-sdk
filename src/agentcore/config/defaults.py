"""Default configuration constants for agentcore-sdk.

``DEFAULT_CONFIG`` provides a baseline ``AgentConfig`` with all features
enabled and sensible values for every field.  It is the starting point used
by ``ConfigLoader.load_auto()`` before applying file or environment overrides.

Shipped in this module
----------------------
- DEFAULT_CONFIG   — ``AgentConfig`` instance with sensible defaults

Extension points
-------------------
Environment-specific config profiles (staging vs production) and dynamic
defaults driven by infrastructure discovery are available via plugins.
"""
from __future__ import annotations

from agentcore.schema.config import AgentConfig

DEFAULT_CONFIG: AgentConfig = AgentConfig(
    agent_name="unnamed-agent",
    agent_version="0.1.0",
    framework="custom",
    model="claude-sonnet-4-5",
    telemetry_enabled=True,
    cost_tracking_enabled=True,
    event_bus_enabled=True,
    plugins=[],
    custom_settings={},
)
"""Baseline ``AgentConfig`` used when no file or env config is present."""
