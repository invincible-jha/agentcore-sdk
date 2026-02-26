"""Unit tests for agentcore.plugins.registry and agentcore.plugins.loader."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentcore.plugins.loader import PluginLoader
from agentcore.plugins.registry import (
    AgentPlugin,
    AgentPluginRegistry,
    PluginAlreadyRegisteredError,
    PluginNotFoundError,
    PluginRegistry,
)
from agentcore.schema.config import AgentConfig


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_null_plugin_class(name: str = "null") -> type[AgentPlugin]:
    """Create a trivial AgentPlugin subclass."""

    class NullPlugin(AgentPlugin):
        def get_name(self) -> str:
            return name

        def initialize(self) -> None:
            pass

        def shutdown(self) -> None:
            pass

    NullPlugin.__name__ = f"NullPlugin_{name}"
    return NullPlugin


# ---------------------------------------------------------------------------
# PluginNotFoundError and PluginAlreadyRegisteredError
# ---------------------------------------------------------------------------

class TestPluginErrors:
    def test_plugin_not_found_error_attributes(self) -> None:
        exc = PluginNotFoundError("my-plugin", "test-registry")
        assert exc.plugin_name == "my-plugin"
        assert exc.registry_name == "test-registry"
        assert isinstance(exc, KeyError)

    def test_plugin_already_registered_error_attributes(self) -> None:
        exc = PluginAlreadyRegisteredError("dup-plugin", "test-registry")
        assert exc.plugin_name == "dup-plugin"
        assert exc.registry_name == "test-registry"
        assert isinstance(exc, ValueError)


# ---------------------------------------------------------------------------
# PluginRegistry[T] — generic registry
# ---------------------------------------------------------------------------

class _BaseABC:
    pass


class TestPluginRegistry:
    def _make_registry(self) -> PluginRegistry[_BaseABC]:
        return PluginRegistry(_BaseABC, "test-reg")

    def test_register_decorator_and_get(self) -> None:
        reg = self._make_registry()

        @reg.register("alpha")
        class AlphaPlugin(_BaseABC):
            pass

        assert reg.get("alpha") is AlphaPlugin

    def test_register_duplicate_raises_already_registered(self) -> None:
        reg = self._make_registry()

        @reg.register("beta")
        class BetaPlugin(_BaseABC):
            pass

        with pytest.raises(PluginAlreadyRegisteredError):
            @reg.register("beta")
            class BetaDuplicate(_BaseABC):
                pass

    def test_register_non_subclass_raises_type_error(self) -> None:
        reg = self._make_registry()
        with pytest.raises(TypeError):
            @reg.register("bad")
            class NotASubclass:  # type: ignore[arg-type]
                pass

    def test_register_class_direct(self) -> None:
        reg = self._make_registry()

        class GammaPlugin(_BaseABC):
            pass

        reg.register_class("gamma", GammaPlugin)
        assert reg.get("gamma") is GammaPlugin

    def test_register_class_duplicate_raises(self) -> None:
        reg = self._make_registry()

        class DeltaPlugin(_BaseABC):
            pass

        reg.register_class("delta", DeltaPlugin)
        with pytest.raises(PluginAlreadyRegisteredError):
            reg.register_class("delta", DeltaPlugin)

    def test_get_unknown_raises_not_found(self) -> None:
        reg = self._make_registry()
        with pytest.raises(PluginNotFoundError):
            reg.get("ghost")

    def test_list_plugins_sorted(self) -> None:
        reg = self._make_registry()

        class Z(_BaseABC):
            pass

        class A(_BaseABC):
            pass

        reg.register_class("z-plugin", Z)
        reg.register_class("a-plugin", A)
        names = reg.list_plugins()
        assert names == sorted(names)

    def test_contains_operator(self) -> None:
        reg = self._make_registry()

        class Plugin(_BaseABC):
            pass

        reg.register_class("p", Plugin)
        assert "p" in reg
        assert "missing" not in reg

    def test_len_operator(self) -> None:
        reg = self._make_registry()
        assert len(reg) == 0

        class P(_BaseABC):
            pass

        reg.register_class("p", P)
        assert len(reg) == 1

    def test_deregister_removes_plugin(self) -> None:
        reg = self._make_registry()

        class E(_BaseABC):
            pass

        reg.register_class("e", E)
        reg.deregister("e")
        assert "e" not in reg

    def test_deregister_unknown_raises_not_found(self) -> None:
        reg = self._make_registry()
        with pytest.raises(PluginNotFoundError):
            reg.deregister("ghost")

    def test_repr_contains_name_and_base_class(self) -> None:
        reg = self._make_registry()
        text = repr(reg)
        assert "test-reg" in text
        assert "_BaseABC" in text

    def test_load_entrypoints_no_entries(self) -> None:
        reg = self._make_registry()
        # With no installed entrypoints in "fake.group", should be a no-op
        reg.load_entrypoints("fake.group.that.doesnt.exist")
        assert len(reg) == 0

    def test_load_entrypoints_skips_already_registered(self) -> None:
        reg = self._make_registry()

        class ExistingPlugin(_BaseABC):
            pass

        reg.register_class("existing", ExistingPlugin)

        mock_ep = MagicMock()
        mock_ep.name = "existing"

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            reg.load_entrypoints("some.group")

        # Should still be one plugin (not duplicated or removed)
        assert len(reg) == 1

    def test_load_entrypoints_skips_failed_load(self) -> None:
        reg = self._make_registry()

        mock_ep = MagicMock()
        mock_ep.name = "failing-ep"
        mock_ep.load.side_effect = ImportError("missing dep")

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            reg.load_entrypoints("some.group")

        assert "failing-ep" not in reg

    def test_load_entrypoints_skips_invalid_class(self) -> None:
        reg = self._make_registry()

        mock_ep = MagicMock()
        mock_ep.name = "bad-class"

        class NotASubclass:
            pass

        mock_ep.load.return_value = NotASubclass

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            reg.load_entrypoints("some.group")

        assert "bad-class" not in reg


# ---------------------------------------------------------------------------
# AgentPluginRegistry
# ---------------------------------------------------------------------------

class TestAgentPluginRegistry:
    def test_register_and_list(self) -> None:
        registry = AgentPluginRegistry()
        NullPlugin = _make_null_plugin_class("null")
        registry.register_plugin("null", NullPlugin)
        assert "null" in registry.list_plugins()

    def test_register_duplicate_raises(self) -> None:
        registry = AgentPluginRegistry()
        NullPlugin = _make_null_plugin_class("n")
        registry.register_plugin("n", NullPlugin)
        with pytest.raises(PluginAlreadyRegisteredError):
            registry.register_plugin("n", NullPlugin)

    def test_register_non_agent_plugin_raises_type_error(self) -> None:
        registry = AgentPluginRegistry()
        with pytest.raises(TypeError):
            registry.register_plugin("bad", object)  # type: ignore[arg-type]

    def test_get_plugin_returns_class(self) -> None:
        registry = AgentPluginRegistry()
        NullPlugin = _make_null_plugin_class("ret")
        registry.register_plugin("ret", NullPlugin)
        assert registry.get_plugin("ret") is NullPlugin

    def test_get_plugin_unknown_raises_not_found(self) -> None:
        registry = AgentPluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.get_plugin("ghost")

    def test_list_plugins_sorted(self) -> None:
        registry = AgentPluginRegistry()
        registry.register_plugin("z", _make_null_plugin_class("z"))
        registry.register_plugin("a", _make_null_plugin_class("a"))
        names = registry.list_plugins()
        assert names == sorted(names)

    def test_len(self) -> None:
        registry = AgentPluginRegistry()
        assert len(registry) == 0
        registry.register_plugin("x", _make_null_plugin_class("x"))
        assert len(registry) == 1

    def test_repr_contains_plugin_names(self) -> None:
        registry = AgentPluginRegistry()
        registry.register_plugin("my-plugin", _make_null_plugin_class("my-plugin"))
        assert "my-plugin" in repr(registry)

    def test_initialize_all_calls_initialize(self) -> None:
        initialized: list[str] = []

        class TrackingPlugin(AgentPlugin):
            def get_name(self) -> str:
                return "tracking"

            def initialize(self) -> None:
                initialized.append("tracking")

            def shutdown(self) -> None:
                pass

        registry = AgentPluginRegistry()
        registry.register_plugin("tracking", TrackingPlugin)
        registry.initialize_all()
        assert "tracking" in initialized

    def test_initialize_all_is_idempotent(self) -> None:
        count = [0]

        class CountPlugin(AgentPlugin):
            def get_name(self) -> str:
                return "count"

            def initialize(self) -> None:
                count[0] += 1

            def shutdown(self) -> None:
                pass

        registry = AgentPluginRegistry()
        registry.register_plugin("count", CountPlugin)
        registry.initialize_all()
        registry.initialize_all()
        assert count[0] == 1  # second call is a no-op

    def test_initialize_all_skips_failing_plugin(self) -> None:
        class GoodPlugin(AgentPlugin):
            def get_name(self) -> str:
                return "good"

            def initialize(self) -> None:
                pass

            def shutdown(self) -> None:
                pass

        class BadPlugin(AgentPlugin):
            def get_name(self) -> str:
                return "bad"

            def initialize(self) -> None:
                raise RuntimeError("init failed")

            def shutdown(self) -> None:
                pass

        registry = AgentPluginRegistry()
        registry.register_plugin("good", GoodPlugin)
        registry.register_plugin("bad", BadPlugin)
        registry.initialize_all()  # must not raise
        # Good plugin should still be initialized
        assert "good" in registry._instances

    def test_shutdown_all_calls_shutdown(self) -> None:
        shut_down: list[str] = []

        class ShutdownPlugin(AgentPlugin):
            def get_name(self) -> str:
                return "sd"

            def initialize(self) -> None:
                pass

            def shutdown(self) -> None:
                shut_down.append("sd")

        registry = AgentPluginRegistry()
        registry.register_plugin("sd", ShutdownPlugin)
        registry.initialize_all()
        registry.shutdown_all()
        assert "sd" in shut_down

    def test_shutdown_all_clears_instances(self) -> None:
        registry = AgentPluginRegistry()
        registry.register_plugin("s", _make_null_plugin_class("s"))
        registry.initialize_all()
        registry.shutdown_all()
        assert registry._instances == {}

    def test_shutdown_all_continues_on_error(self) -> None:
        class FailShutdownPlugin(AgentPlugin):
            def get_name(self) -> str:
                return "fs"

            def initialize(self) -> None:
                pass

            def shutdown(self) -> None:
                raise RuntimeError("shutdown exploded")

        registry = AgentPluginRegistry()
        registry.register_plugin("fs", FailShutdownPlugin)
        registry.initialize_all()
        registry.shutdown_all()  # must not raise

    def test_auto_discover_no_entrypoints(self) -> None:
        registry = AgentPluginRegistry()
        discovered = registry.auto_discover("nonexistent.group")
        assert discovered == []


# ---------------------------------------------------------------------------
# PluginLoader
# ---------------------------------------------------------------------------

class TestPluginLoader:
    def test_load_from_entry_points_no_entries(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)
        with patch("importlib.metadata.entry_points", return_value=[]):
            loaded = loader.load_from_entry_points()
        assert loaded == []

    def test_load_from_entry_points_valid_plugin(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        NullPlugin = _make_null_plugin_class("ep-plugin")

        mock_ep = MagicMock()
        mock_ep.name = "ep-plugin"
        mock_ep.load.return_value = NullPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            loaded = loader.load_from_entry_points()

        assert "ep-plugin" in loaded

    def test_load_from_entry_points_skips_failed_load(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        mock_ep = MagicMock()
        mock_ep.name = "fail-ep"
        mock_ep.load.side_effect = ImportError("missing")

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            loaded = loader.load_from_entry_points()

        assert "fail-ep" not in loaded

    def test_load_from_entry_points_skips_non_agent_plugin_class(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        class NotAnAgentPlugin:
            pass

        mock_ep = MagicMock()
        mock_ep.name = "not-agent-plugin"
        mock_ep.load.return_value = NotAnAgentPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            loaded = loader.load_from_entry_points()

        assert "not-agent-plugin" not in loaded

    def test_load_from_path_nonexistent_raises_plugin_error(self) -> None:
        from agentcore.schema.errors import PluginError
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)
        with pytest.raises(PluginError, match="not found"):
            loader.load_from_path("/nonexistent/path/plugin.py")

    def test_load_from_path_valid_plugin_module(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        plugin_code = """
from agentcore.plugins.registry import AgentPlugin

class FilePlugin(AgentPlugin):
    def get_name(self):
        return "file-plugin"
    def initialize(self):
        pass
    def shutdown(self):
        pass
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(plugin_code)
            temp_path = f.name

        try:
            loaded = loader.load_from_path(temp_path)
            assert "file-plugin" in loaded
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_from_config_empty_plugins_returns_empty(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)
        config = AgentConfig(plugins=[])
        loaded = loader.load_from_config(config)
        assert loaded == []

    def test_load_from_config_filters_by_allowed_names(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        NullPlugin = _make_null_plugin_class("allowed-plugin")

        mock_ep = MagicMock()
        mock_ep.name = "allowed-plugin"
        mock_ep.load.return_value = NullPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            # Config only allows "allowed-plugin"
            config = AgentConfig(plugins=["allowed-plugin"])
            loaded = loader.load_from_config(config)

        assert "allowed-plugin" in loaded

    def test_load_from_config_excludes_unlisted_plugins(self) -> None:
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        NullPlugin = _make_null_plugin_class("other-plugin")

        mock_ep = MagicMock()
        mock_ep.name = "other-plugin"
        mock_ep.load.return_value = NullPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            config = AgentConfig(plugins=["allowed-only"])
            loaded = loader.load_from_config(config)

        assert "other-plugin" not in loaded

    def test_load_from_entry_points_skips_registration_error(self) -> None:
        """Covers loader.py lines 90-91: exception during register_plugin."""
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        NullPlugin = _make_null_plugin_class("dup-reg")
        # Pre-register so that the second registration raises PluginAlreadyRegisteredError,
        # but PluginLoader catches all exceptions (lines 90-91).
        registry.register_plugin("dup-reg", NullPlugin)

        mock_ep = MagicMock()
        mock_ep.name = "dup-reg"
        mock_ep.load.return_value = NullPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            loaded = loader.load_from_entry_points()

        # The pre-registered plugin was already there; loader skipped re-registration
        assert "dup-reg" not in loaded

    def test_load_from_path_bad_module_spec_raises_plugin_error(self) -> None:
        """Covers loader.py lines 129-133: spec_from_file_location returns None."""
        from agentcore.schema.errors import PluginError
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            temp_path = f.name
            f.write(b"# empty\n")

        try:
            with patch("importlib.util.spec_from_file_location", return_value=None):
                with pytest.raises(PluginError, match="spec"):
                    loader.load_from_path(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_from_path_exec_failure_raises_plugin_error(self) -> None:
        """Covers loader.py lines 138-142: exec_module raises an exception."""
        from agentcore.schema.errors import PluginError
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            temp_path = f.name
            f.write(b"raise RuntimeError('intentional')\n")

        try:
            with pytest.raises(PluginError, match="Failed to execute"):
                loader.load_from_path(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_from_path_skips_class_that_fails_instantiation(self) -> None:
        """Covers loader.py lines 158-163: exception when instantiating plugin class."""
        registry = AgentPluginRegistry()
        loader = PluginLoader(registry)

        plugin_code = """
from agentcore.plugins.registry import AgentPlugin

class BrokenPlugin(AgentPlugin):
    def __init__(self):
        raise RuntimeError("cannot instantiate")
    def get_name(self):
        return "broken"
    def initialize(self):
        pass
    def shutdown(self):
        pass
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(plugin_code)
            temp_path = f.name

        try:
            loaded = loader.load_from_path(temp_path)
            assert "broken" not in loaded
        finally:
            Path(temp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AgentPluginRegistry.auto_discover — missing branches
# ---------------------------------------------------------------------------

class TestAgentPluginRegistryAutoDiscover:
    def test_auto_discover_skips_already_registered(self) -> None:
        """Covers registry.py lines 411-414: ep.name already in _classes."""
        registry = AgentPluginRegistry()
        NullPlugin = _make_null_plugin_class("pre-registered")
        registry.register_plugin("pre-registered", NullPlugin)

        mock_ep = MagicMock()
        mock_ep.name = "pre-registered"

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            discovered = registry.auto_discover("some.group")

        assert "pre-registered" not in discovered
        # load() was never called because we short-circuited
        mock_ep.load.assert_not_called()

    def test_auto_discover_skips_non_agent_plugin_subclass(self) -> None:
        """Covers registry.py lines 420-422: loaded class is not AgentPlugin subclass."""
        registry = AgentPluginRegistry()

        class NotAnAgentPlugin:
            pass

        mock_ep = MagicMock()
        mock_ep.name = "not-plugin"
        mock_ep.load.return_value = NotAnAgentPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            discovered = registry.auto_discover("some.group")

        assert "not-plugin" not in discovered

    def test_auto_discover_skips_failed_ep_load(self) -> None:
        """Covers registry.py lines 415-419: ep.load() raises."""
        registry = AgentPluginRegistry()

        mock_ep = MagicMock()
        mock_ep.name = "exploding-ep"
        mock_ep.load.side_effect = ImportError("missing package")

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            discovered = registry.auto_discover("some.group")

        assert "exploding-ep" not in discovered

    def test_auto_discover_handles_already_registered_race(self) -> None:
        """Covers registry.py lines 423-427: PluginAlreadyRegisteredError during register."""
        registry = AgentPluginRegistry()
        NullPlugin = _make_null_plugin_class("race-plugin")

        # Simulate the race: ep.name is NOT in _classes at the lock check, but
        # register_plugin raises PluginAlreadyRegisteredError anyway (e.g., race).
        mock_ep = MagicMock()
        mock_ep.name = "race-plugin"
        mock_ep.load.return_value = NullPlugin

        original_register = registry.register_plugin

        def _raise_on_register(name: str, cls: type) -> None:
            from agentcore.plugins.registry import PluginAlreadyRegisteredError
            raise PluginAlreadyRegisteredError(name, "AgentPluginRegistry")

        registry.register_plugin = _raise_on_register  # type: ignore[method-assign]

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            discovered = registry.auto_discover("some.group")

        # Exception was swallowed; plugin not reported as discovered
        assert "race-plugin" not in discovered
