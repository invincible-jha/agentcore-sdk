"""Plugin loader for agentcore-sdk.

Discovers and loads ``AgentPlugin`` implementations from entry-points,
filesystem paths, or configuration objects.

Shipped in this module
----------------------
- PluginLoader   — discovers and loads plugins from multiple sources

Extension points
-------------------
Sandboxed plugin execution, cryptographic plugin signing, and remote plugin
registries are not part of this open-source SDK.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import logging
from pathlib import Path

from agentcore.plugins.registry import AgentPlugin, AgentPluginRegistry
from agentcore.schema.config import AgentConfig
from agentcore.schema.errors import PluginError

logger = logging.getLogger(__name__)


class PluginLoader:
    """Discovers and registers ``AgentPlugin`` implementations.

    All loaded plugins are registered into the supplied
    :class:`~agentcore.plugins.registry.AgentPluginRegistry`.

    Parameters
    ----------
    registry:
        The plugin registry to populate.

    Examples
    --------
    >>> registry = AgentPluginRegistry()
    >>> loader = PluginLoader(registry)
    >>> loader.load_from_entry_points()  # loads installed agentcore plugins
    """

    def __init__(self, registry: AgentPluginRegistry) -> None:
        self._registry = registry

    def load_from_entry_points(
        self, group: str = "agentcore.plugins"
    ) -> list[str]:
        """Discover and register plugins declared as package entry-points.

        Parameters
        ----------
        group:
            Entry-point group name.  Defaults to ``"agentcore.plugins"``.

        Returns
        -------
        list[str]
            Names of successfully loaded plugins.
        """
        loaded: list[str] = []
        entry_points = importlib.metadata.entry_points(group=group)
        for ep in entry_points:
            try:
                cls = ep.load()
            except Exception:
                logger.exception(
                    "Failed to load entry-point %r from group %r; skipping.",
                    ep.name,
                    group,
                )
                continue

            if not (isinstance(cls, type) and issubclass(cls, AgentPlugin)):
                logger.warning(
                    "Entry-point %r does not subclass AgentPlugin; skipping.",
                    ep.name,
                )
                continue

            try:
                self._registry.register_plugin(ep.name, cls)
                loaded.append(ep.name)
                logger.info("Loaded plugin %r from entry-point.", ep.name)
            except Exception:
                logger.warning(
                    "Could not register plugin %r from entry-point; skipping.",
                    ep.name,
                )

        return loaded

    def load_from_path(self, path: str | Path) -> list[str]:
        """Load plugins by importing a Python module from *path*.

        The module is expected to contain one or more classes that subclass
        :class:`~agentcore.plugins.registry.AgentPlugin`.  All such classes
        are registered under their ``get_name()`` return value.

        Parameters
        ----------
        path:
            Path to a ``.py`` file.

        Returns
        -------
        list[str]
            Names of successfully loaded plugins.

        Raises
        ------
        PluginError
            If the module cannot be loaded.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise PluginError(
                f"Plugin module not found: {resolved}",
                context={"path": str(resolved)},
            )

        module_name = resolved.stem
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise PluginError(
                f"Could not create module spec for {resolved}.",
                context={"path": str(resolved)},
            )

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:
            raise PluginError(
                f"Failed to execute module {resolved}: {exc}",
                context={"path": str(resolved)},
            ) from exc

        loaded: list[str] = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, AgentPlugin)
                and attr is not AgentPlugin
            ):
                try:
                    instance = attr()
                    plugin_name = instance.get_name()
                    self._registry.register_plugin(plugin_name, attr)
                    loaded.append(plugin_name)
                    logger.info("Loaded plugin %r from path %s.", plugin_name, resolved)
                except Exception:
                    logger.warning(
                        "Could not register plugin class %r from %s; skipping.",
                        attr_name,
                        resolved,
                    )

        return loaded

    def load_from_config(self, config: AgentConfig) -> list[str]:
        """Load plugins listed in *config.plugins* from entry-points.

        Only plugins whose names appear in ``config.plugins`` are loaded.
        This allows callers to restrict auto-discovery to an explicit
        allowlist.

        Parameters
        ----------
        config:
            Validated agent configuration.

        Returns
        -------
        list[str]
            Names of successfully loaded plugins.
        """
        if not config.plugins:
            return []

        all_loaded = self.load_from_entry_points()
        return [name for name in all_loaded if name in config.plugins]
