"""Plugin subsystem for agentcore-sdk.

Provides two registry systems:

- :class:`PluginRegistry` — generic type-safe decorator registry for any ABC
- :class:`AgentPluginRegistry` — lifecycle-managed registry for AgentPlugins

Third-party implementations register via entry-points under the
``"agentcore.plugins"`` group in their ``pyproject.toml``.

Example — declaring a plugin in pyproject.toml
----------------------------------------------
.. code-block:: toml

    [project.entry-points."agentcore.plugins"]
    my_plugin = "my_package.plugins.my_plugin:MyPlugin"
"""
from __future__ import annotations

from agentcore.plugins.loader import PluginLoader
from agentcore.plugins.registry import (
    AgentPlugin,
    AgentPluginRegistry,
    PluginAlreadyRegisteredError,
    PluginNotFoundError,
    PluginRegistry,
)

__all__ = [
    "PluginRegistry",
    "AgentPlugin",
    "AgentPluginRegistry",
    "PluginLoader",
    "PluginNotFoundError",
    "PluginAlreadyRegisteredError",
]
