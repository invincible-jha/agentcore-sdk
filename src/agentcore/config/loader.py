"""Configuration loader for agentcore-sdk.

``ConfigLoader`` resolves configuration from YAML files, JSON files,
environment variables, or auto-discovers the first available source by
searching well-known paths.

Shipped in this module
----------------------
- ConfigLoader   — multi-source config loader with auto-discovery

Extension points
-------------------
Remote config from AWS Secrets Manager / GCP Secret Manager, config hot-reload
with inotify, and encrypted field decryption are available via plugins.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import yaml

from agentcore.config.defaults import DEFAULT_CONFIG
from agentcore.config.schema import validate_config
from agentcore.schema.config import AgentConfig
from agentcore.schema.errors import ConfigurationError

logger = logging.getLogger(__name__)

# Ordered list of paths searched by load_auto()
_AUTO_SEARCH_PATHS: tuple[str, ...] = (
    "agentcore.yaml",
    "agentcore.yml",
    "agentcore.json",
    ".agentcore.yaml",
    ".agentcore.yml",
    ".agentcore.json",
)


class ConfigLoader:
    """Loads ``AgentConfig`` from multiple sources.

    All loader methods return a validated ``AgentConfig`` instance.  Callers
    can chain loaders by calling ``config.merge(other_config)`` on the
    result.

    Examples
    --------
    >>> loader = ConfigLoader()
    >>> config = loader.load_env()
    >>> config.agent_name
    'unnamed-agent'
    """

    def load_yaml(self, path: str | Path) -> AgentConfig:
        """Load configuration from a YAML file.

        Parameters
        ----------
        path:
            Path to a YAML config file.

        Returns
        -------
        AgentConfig

        Raises
        ------
        ConfigurationError
            If the file cannot be read or fails validation.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise ConfigurationError(
                f"YAML config file not found: {resolved}",
                context={"path": str(resolved)},
            )
        try:
            with resolved.open(encoding="utf-8") as fh:
                raw: object = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ConfigurationError(
                f"Failed to parse YAML config at {resolved}: {exc}",
                context={"path": str(resolved)},
            ) from exc

        data: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
        logger.debug("Loaded YAML config from %s", resolved)
        return validate_config(data)

    def load_json(self, path: str | Path) -> AgentConfig:
        """Load configuration from a JSON file.

        Parameters
        ----------
        path:
            Path to a JSON config file.

        Returns
        -------
        AgentConfig

        Raises
        ------
        ConfigurationError
            If the file cannot be read or fails validation.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise ConfigurationError(
                f"JSON config file not found: {resolved}",
                context={"path": str(resolved)},
            )
        try:
            with resolved.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"Failed to parse JSON config at {resolved}: {exc}",
                context={"path": str(resolved)},
            ) from exc

        data = dict(raw) if isinstance(raw, dict) else {}
        logger.debug("Loaded JSON config from %s", resolved)
        return validate_config(data)

    def load_env(self, prefix: str = "AGENTCORE_") -> AgentConfig:
        """Build configuration from environment variables.

        See :meth:`~agentcore.schema.config.AgentConfig.from_env` for
        variable mapping rules.

        Parameters
        ----------
        prefix:
            Environment variable prefix.  Defaults to ``"AGENTCORE_"``.

        Returns
        -------
        AgentConfig
        """
        config = AgentConfig.from_env(prefix=prefix)
        logger.debug("Loaded config from environment with prefix %r", prefix)
        return config

    def load_auto(
        self,
        search_dir: str | Path | None = None,
        env_prefix: str = "AGENTCORE_",
    ) -> AgentConfig:
        """Auto-discover and load configuration.

        Discovery order:

        1. Search *search_dir* (defaults to ``cwd``) for ``agentcore.yaml``,
           ``agentcore.yml``, ``agentcore.json``, and hidden variants.
        2. Overlay environment variables from *env_prefix* on top.
        3. Fall back to ``DEFAULT_CONFIG`` if nothing is found.

        Parameters
        ----------
        search_dir:
            Directory to search.  Defaults to the current working directory.
        env_prefix:
            Environment variable prefix for overlay.

        Returns
        -------
        AgentConfig
        """
        base_dir = Path(search_dir) if search_dir is not None else Path.cwd()
        base_config: AgentConfig | None = None

        for candidate_name in _AUTO_SEARCH_PATHS:
            candidate = base_dir / candidate_name
            if not candidate.exists():
                continue
            try:
                if candidate.suffix in {".yaml", ".yml"}:
                    base_config = self.load_yaml(candidate)
                else:
                    base_config = self.load_json(candidate)
                logger.info("Auto-loaded agentcore config from %s", candidate)
                break
            except ConfigurationError:
                logger.warning("Could not load config from %s; trying next.", candidate)

        if base_config is None:
            base_config = DEFAULT_CONFIG
            logger.debug("No config file found; using DEFAULT_CONFIG.")

        # Apply env overrides
        env_has_any = any(k.startswith(env_prefix) for k in os.environ)
        if env_has_any:
            env_config = self.load_env(prefix=env_prefix)
            base_config = base_config.merge(env_config)
            logger.debug("Applied environment variable overlay.")

        return base_config
