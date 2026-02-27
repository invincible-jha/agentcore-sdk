"""Agent configuration schema for agentcore-sdk.

``AgentConfig`` is a Pydantic v2 model that acts as the validated,
strongly-typed boundary object between raw configuration sources (YAML files,
environment variables, in-memory dicts) and the rest of the SDK.

Shipped in this module
----------------------
- AgentConfig     — Pydantic v2 model with class-method loaders

Extension points
-------------------
Remote config fetching, encrypted secrets support, multi-environment
configuration overlays, and hot-reload capabilities are available via plugins.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class AgentConfig(BaseModel):
    """Validated runtime configuration for an agentcore-powered agent.

    All fields have sensible defaults so that an agent can start with zero
    configuration and progressively opt-in to features.

    Parameters
    ----------
    agent_name:
        Human-readable name; defaults to ``"unnamed-agent"``.
    agent_version:
        SemVer string; defaults to ``"0.1.0"``.
    framework:
        Agent framework identifier (e.g. ``"langchain"``, ``"crewai"``).
    model:
        Primary LLM identifier (e.g. ``"claude-sonnet-4-5"``).
    telemetry_enabled:
        Whether OpenTelemetry spans/metrics are emitted.
    cost_tracking_enabled:
        Whether token-cost accounting is active.
    event_bus_enabled:
        Whether the event bus is active.
    plugins:
        List of plugin names to auto-load at startup.
    custom_settings:
        Arbitrary key/value store for framework-specific or user settings.
    """

    model_config = {"extra": "allow", "validate_assignment": True}

    agent_name: str = Field(default="unnamed-agent")
    agent_version: str = Field(default="0.1.0")
    framework: str = Field(default="custom")
    model: str = Field(default="claude-sonnet-4-5")
    telemetry_enabled: bool = Field(default=True)
    cost_tracking_enabled: bool = Field(default=True)
    event_bus_enabled: bool = Field(default=True)
    plugins: list[str] = Field(default_factory=list)
    custom_settings: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalise_plugins(cls, values: Any) -> Any:  # noqa: ANN401
        """Ensure ``plugins`` is always a list, not None."""
        if isinstance(values, dict) and values.get("plugins") is None:
            values["plugins"] = []
        return values

    # ------------------------------------------------------------------
    # Class-method loaders
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AgentConfig":
        """Load and validate configuration from a YAML file.

        Parameters
        ----------
        path:
            Filesystem path to a YAML file.

        Returns
        -------
        AgentConfig

        Raises
        ------
        FileNotFoundError
            If ``path`` does not exist.
        pydantic.ValidationError
            If the parsed data fails validation.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Config file not found: {resolved}")
        with resolved.open(encoding="utf-8") as fh:
            raw: object = yaml.safe_load(fh)
        data: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
        return cls.model_validate(data)

    @classmethod
    def from_env(cls, prefix: str = "AGENTCORE_") -> "AgentConfig":
        """Build configuration from environment variables.

        Variables are mapped by stripping the ``prefix`` and lower-casing the
        remainder.  For example ``AGENTCORE_AGENT_NAME=mybot`` maps to
        ``agent_name="mybot"``.

        Boolean values accept ``"true"`` / ``"1"`` / ``"yes"`` as truthy and
        anything else as falsy (case-insensitive).

        Parameters
        ----------
        prefix:
            Environment variable prefix to scan.  Defaults to
            ``"AGENTCORE_"``.

        Returns
        -------
        AgentConfig
        """
        data: dict[str, object] = {}
        bool_fields = {"telemetry_enabled", "cost_tracking_enabled", "event_bus_enabled"}
        list_fields = {"plugins"}

        for raw_key, raw_value in os.environ.items():
            if not raw_key.startswith(prefix):
                continue
            key = raw_key[len(prefix):].lower()
            if key in bool_fields:
                data[key] = raw_value.lower() in {"true", "1", "yes"}
            elif key in list_fields:
                # Accept comma-separated values
                data[key] = [item.strip() for item in raw_value.split(",") if item.strip()]
            elif key == "custom_settings":
                try:
                    parsed = json.loads(raw_value)
                    data[key] = parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    data[key] = {}
            else:
                data[key] = raw_value

        return cls.model_validate(data)

    def merge(self, overrides: "AgentConfig") -> "AgentConfig":
        """Produce a new ``AgentConfig`` with non-default values from *overrides*.

        Fields in *overrides* that differ from the class default take
        precedence over the corresponding field in *self*.  The ``plugins``
        and ``custom_settings`` collections are merged (union/update) rather
        than replaced outright.

        Parameters
        ----------
        overrides:
            Another ``AgentConfig`` whose non-default values win.

        Returns
        -------
        AgentConfig
            New, merged configuration.  Neither *self* nor *overrides* is
            mutated.
        """
        base_data = self.model_dump()
        override_data = overrides.model_dump()

        default = AgentConfig()
        default_data = default.model_dump()

        merged = dict(base_data)
        for key, override_value in override_data.items():
            if override_value != default_data.get(key):
                if key == "plugins":
                    existing = merged.get("plugins", [])
                    existing_list: list[str] = list(existing) if isinstance(existing, list) else []
                    override_list: list[str] = (
                        list(override_value) if isinstance(override_value, list) else []
                    )
                    # Union while preserving order
                    seen: set[str] = set(existing_list)
                    for item in override_list:
                        if item not in seen:
                            existing_list.append(item)
                            seen.add(item)
                    merged["plugins"] = existing_list
                elif key == "custom_settings":
                    base_settings = dict(merged.get("custom_settings", {}))  # type: ignore[arg-type]
                    if isinstance(override_value, dict):
                        base_settings.update(override_value)
                    merged["custom_settings"] = base_settings
                else:
                    merged[key] = override_value

        return AgentConfig.model_validate(merged)
