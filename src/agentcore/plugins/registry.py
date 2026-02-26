"""Plugin registry for agentcore-sdk.

Provides two complementary registry systems:

1. ``PluginRegistry[T]`` — the original generic, type-safe decorator registry
   for any abstract base class.  This is the low-level primitive used by
   third-party packages to register arbitrary plugin types.

2. ``AgentPlugin`` + ``AgentPluginRegistry`` — a higher-level, opinionated
   system for agentcore lifecycle plugins with ``initialize``, ``shutdown``,
   and ``get_name`` contracts.

Shipped in this module
----------------------
- PluginNotFoundError          — lookup failure
- PluginAlreadyRegisteredError — duplicate registration
- PluginRegistry[T]            — generic type-safe decorator registry
- AgentPlugin                  — ABC for lifecycle plugins
- AgentPluginRegistry          — registry + lifecycle management for AgentPlugins

Withheld / internal
-------------------
Sandboxed plugin execution, cryptographic signing, and remote plugin
registries are not part of this open-source SDK.

Example — generic registry
--------------------------
Define a base class and registry::

    from abc import ABC, abstractmethod
    from agentcore.plugins.registry import PluginRegistry

    class BaseProcessor(ABC):
        @abstractmethod
        def process(self, data: bytes) -> bytes: ...

    processor_registry: PluginRegistry[BaseProcessor] = PluginRegistry(
        BaseProcessor, "processors"
    )

Register a plugin with the decorator::

    @processor_registry.register("my-processor")
    class MyProcessor(BaseProcessor):
        def process(self, data: bytes) -> bytes:
            return data.upper()

Example — AgentPlugin
---------------------
::

    from agentcore.plugins.registry import AgentPlugin, AgentPluginRegistry

    class LoggingPlugin(AgentPlugin):
        def get_name(self) -> str:
            return "logging-plugin"

        def initialize(self) -> None:
            print("LoggingPlugin started")

        def shutdown(self) -> None:
            print("LoggingPlugin stopped")

    registry = AgentPluginRegistry()
    registry.register_plugin("logging-plugin", LoggingPlugin)
    registry.initialize_all()
"""
from __future__ import annotations

import importlib.metadata
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=ABC)


# ---------------------------------------------------------------------------
# Shared exceptions
# ---------------------------------------------------------------------------


class PluginNotFoundError(KeyError):
    """Raised when a requested plugin name is not in the registry."""

    def __init__(self, name: str, registry_name: str) -> None:
        self.plugin_name = name
        self.registry_name = registry_name
        super().__init__(
            f"Plugin {name!r} is not registered in the {registry_name!r} registry. "
            f"Available plugins: {name!r} was not found. "
            "Check that the package is installed and its entry-points are declared."
        )


class PluginAlreadyRegisteredError(ValueError):
    """Raised when attempting to register a name that already exists."""

    def __init__(self, name: str, registry_name: str) -> None:
        self.plugin_name = name
        self.registry_name = registry_name
        super().__init__(
            f"Plugin {name!r} is already registered in the {registry_name!r} registry. "
            "Use a unique name or explicitly deregister the existing entry first."
        )


# ---------------------------------------------------------------------------
# Generic PluginRegistry[T]
# ---------------------------------------------------------------------------


class PluginRegistry(Generic[T]):
    """Type-safe registry for plugin implementations.

    Plugins are registered either via the ``@register`` decorator at
    import time, or lazily via ``load_entrypoints`` for installed packages.

    Parameters
    ----------
    base_class:
        The abstract base class all plugins must subclass.
    name:
        A human-readable name for this registry (used in error messages).
    """

    def __init__(self, base_class: type[T], name: str) -> None:
        self._base_class = base_class
        self._name = name
        self._plugins: dict[str, type[T]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        """Return a class decorator that registers the decorated class.

        Parameters
        ----------
        name:
            The unique string key for this plugin.

        Returns
        -------
        Callable[[type[T]], type[T]]
            A decorator that registers the class and returns it unchanged.

        Raises
        ------
        PluginAlreadyRegisteredError
            If ``name`` is already in use in this registry.
        TypeError
            If the decorated class does not subclass ``base_class``.
        """

        def decorator(cls: type[T]) -> type[T]:
            if name in self._plugins:
                raise PluginAlreadyRegisteredError(name, self._name)
            if not (isinstance(cls, type) and issubclass(cls, self._base_class)):
                raise TypeError(
                    f"Cannot register {cls!r} under {name!r}: "
                    f"it must be a subclass of {self._base_class.__name__}."
                )
            self._plugins[name] = cls
            logger.debug(
                "Registered plugin %r -> %s in registry %r",
                name,
                cls.__qualname__,
                self._name,
            )
            return cls

        return decorator

    def register_class(self, name: str, cls: type[T]) -> None:
        """Register a class directly without using the decorator syntax."""
        if name in self._plugins:
            raise PluginAlreadyRegisteredError(name, self._name)
        if not (isinstance(cls, type) and issubclass(cls, self._base_class)):
            raise TypeError(
                f"Cannot register {cls!r} under {name!r}: "
                f"it must be a subclass of {self._base_class.__name__}."
            )
        self._plugins[name] = cls
        logger.debug(
            "Registered plugin %r -> %s in registry %r",
            name,
            cls.__qualname__,
            self._name,
        )

    def deregister(self, name: str) -> None:
        """Remove a plugin from the registry."""
        if name not in self._plugins:
            raise PluginNotFoundError(name, self._name)
        del self._plugins[name]
        logger.debug("Deregistered plugin %r from registry %r", name, self._name)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> type[T]:
        """Return the class registered under ``name``."""
        try:
            return self._plugins[name]
        except KeyError:
            raise PluginNotFoundError(name, self._name) from None

    def list_plugins(self) -> list[str]:
        """Return a sorted list of all registered plugin names."""
        return sorted(self._plugins)

    def __contains__(self, name: object) -> bool:
        return name in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)

    def __repr__(self) -> str:
        return (
            f"PluginRegistry(name={self._name!r}, "
            f"base_class={self._base_class.__name__}, "
            f"plugins={self.list_plugins()})"
        )

    # ------------------------------------------------------------------
    # Entry-point loading
    # ------------------------------------------------------------------

    def load_entrypoints(self, group: str) -> None:
        """Discover and register plugins declared as package entry-points.

        Parameters
        ----------
        group:
            The entry-point group name, e.g. ``"agentcore.plugins"``.
        """
        entry_points = importlib.metadata.entry_points(group=group)
        for ep in entry_points:
            if ep.name in self._plugins:
                logger.debug(
                    "Entry-point %r already registered in %r; skipping.",
                    ep.name,
                    self._name,
                )
                continue
            try:
                cls = ep.load()
            except Exception:
                logger.exception(
                    "Failed to load entry-point %r from group %r; skipping.",
                    ep.name,
                    group,
                )
                continue
            try:
                self.register_class(ep.name, cls)
            except (PluginAlreadyRegisteredError, TypeError):
                logger.warning(
                    "Entry-point %r loaded but could not be registered "
                    "in registry %r; skipping.",
                    ep.name,
                    self._name,
                )


# ---------------------------------------------------------------------------
# AgentPlugin ABC + AgentPluginRegistry
# ---------------------------------------------------------------------------


class AgentPlugin(ABC):
    """Abstract base class for agentcore lifecycle plugins.

    A plugin participates in the agent's startup/shutdown lifecycle and
    must implement three methods: :meth:`get_name`, :meth:`initialize`,
    and :meth:`shutdown`.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return the canonical plugin name.

        Returns
        -------
        str
            A stable, unique plugin identifier.
        """

    @abstractmethod
    def initialize(self) -> None:
        """Called when the plugin is activated.

        Implementors should perform any setup here (e.g. open connections,
        register event subscribers).  Must be idempotent.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Called when the plugin is deactivated.

        Implementors should release resources here.  Must be idempotent.
        """


class AgentPluginRegistry:
    """Thread-safe registry for :class:`AgentPlugin` implementations.

    Manages the full lifecycle: registration, discovery, initialisation,
    and shutdown of all installed plugins.

    Examples
    --------
    >>> registry = AgentPluginRegistry()
    >>> class NullPlugin(AgentPlugin):
    ...     def get_name(self) -> str: return "null"
    ...     def initialize(self) -> None: pass
    ...     def shutdown(self) -> None: pass
    >>> registry.register_plugin("null", NullPlugin)
    >>> registry.list_plugins()
    ['null']
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._classes: dict[str, type[AgentPlugin]] = {}
        self._instances: dict[str, AgentPlugin] = {}

    def register_plugin(self, name: str, plugin_cls: type[AgentPlugin]) -> None:
        """Register a plugin class under *name*.

        Parameters
        ----------
        name:
            Unique plugin identifier.
        plugin_cls:
            Class that subclasses :class:`AgentPlugin`.

        Raises
        ------
        PluginAlreadyRegisteredError
            If *name* is already registered.
        TypeError
            If *plugin_cls* is not a subclass of ``AgentPlugin``.
        """
        if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, AgentPlugin)):
            raise TypeError(
                f"Cannot register {plugin_cls!r}: "
                "it must be a subclass of AgentPlugin."
            )
        with self._lock:
            if name in self._classes:
                raise PluginAlreadyRegisteredError(name, "AgentPluginRegistry")
            self._classes[name] = plugin_cls
        logger.debug("Registered AgentPlugin %r -> %s", name, plugin_cls.__qualname__)

    def get_plugin(self, name: str) -> type[AgentPlugin]:
        """Return the plugin *class* registered under *name*.

        Parameters
        ----------
        name:
            Plugin identifier.

        Returns
        -------
        type[AgentPlugin]

        Raises
        ------
        PluginNotFoundError
            If *name* is not registered.
        """
        with self._lock:
            if name not in self._classes:
                raise PluginNotFoundError(name, "AgentPluginRegistry")
            return self._classes[name]

    def list_plugins(self) -> list[str]:
        """Return a sorted list of all registered plugin names.

        Returns
        -------
        list[str]
        """
        with self._lock:
            return sorted(self._classes)

    def auto_discover(self, group: str = "agentcore.plugins") -> list[str]:
        """Discover plugins via ``importlib.metadata`` entry-points.

        Parameters
        ----------
        group:
            Entry-point group to scan.

        Returns
        -------
        list[str]
            Names of newly registered plugins.
        """
        discovered: list[str] = []
        entry_points = importlib.metadata.entry_points(group=group)
        for ep in entry_points:
            with self._lock:
                if ep.name in self._classes:
                    logger.debug("Plugin %r already registered; skipping.", ep.name)
                    continue
            try:
                cls = ep.load()
            except Exception:
                logger.exception("Failed to load plugin %r; skipping.", ep.name)
                continue
            if not (isinstance(cls, type) and issubclass(cls, AgentPlugin)):
                logger.warning("Plugin %r is not an AgentPlugin subclass; skipping.", ep.name)
                continue
            try:
                self.register_plugin(ep.name, cls)
                discovered.append(ep.name)
            except PluginAlreadyRegisteredError:
                pass
        return discovered

    def initialize_all(self) -> None:
        """Instantiate and initialise all registered plugins.

        Plugins that raise during ``initialize()`` are logged and skipped;
        they do not prevent other plugins from starting.
        """
        with self._lock:
            classes = dict(self._classes)

        for name, cls in classes.items():
            if name in self._instances:
                continue
            try:
                instance = cls()
                instance.initialize()
                with self._lock:
                    self._instances[name] = instance
                logger.info("Initialized plugin %r.", name)
            except Exception:
                logger.exception("Plugin %r failed to initialize; skipping.", name)

    def shutdown_all(self) -> None:
        """Shut down and remove all active plugin instances.

        Plugins that raise during ``shutdown()`` are logged; shutdown
        continues for remaining plugins.
        """
        with self._lock:
            instances = dict(self._instances)
            self._instances.clear()

        for name, instance in instances.items():
            try:
                instance.shutdown()
                logger.info("Shut down plugin %r.", name)
            except Exception:
                logger.exception("Plugin %r raised during shutdown.", name)

    def __len__(self) -> int:
        with self._lock:
            return len(self._classes)

    def __repr__(self) -> str:
        return f"AgentPluginRegistry(plugins={self.list_plugins()})"
