"""Unit tests for agentcore.schema.config (AgentConfig).

Tests cover construction with defaults, YAML/env loading, merge semantics,
and validation behaviour.
"""
from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from agentcore.schema.config import AgentConfig


# ---------------------------------------------------------------------------
# Default construction
# ---------------------------------------------------------------------------


class TestAgentConfigDefaults:
    def test_default_agent_name(self) -> None:
        cfg = AgentConfig()
        assert cfg.agent_name == "unnamed-agent"

    def test_default_agent_version(self) -> None:
        cfg = AgentConfig()
        assert cfg.agent_version == "0.1.0"

    def test_default_framework(self) -> None:
        cfg = AgentConfig()
        assert cfg.framework == "custom"

    def test_default_model(self) -> None:
        cfg = AgentConfig()
        assert cfg.model == "claude-sonnet-4-5"

    def test_telemetry_enabled_default_true(self) -> None:
        cfg = AgentConfig()
        assert cfg.telemetry_enabled is True

    def test_cost_tracking_enabled_default_true(self) -> None:
        cfg = AgentConfig()
        assert cfg.cost_tracking_enabled is True

    def test_event_bus_enabled_default_true(self) -> None:
        cfg = AgentConfig()
        assert cfg.event_bus_enabled is True

    def test_plugins_default_empty_list(self) -> None:
        cfg = AgentConfig()
        assert cfg.plugins == []

    def test_custom_settings_default_empty_dict(self) -> None:
        cfg = AgentConfig()
        assert cfg.custom_settings == {}

    def test_none_plugins_normalised_to_empty_list(self) -> None:
        cfg = AgentConfig(plugins=None)  # type: ignore[arg-type]
        assert cfg.plugins == []


# ---------------------------------------------------------------------------
# Explicit field construction
# ---------------------------------------------------------------------------


class TestAgentConfigExplicitFields:
    def test_custom_agent_name(self) -> None:
        cfg = AgentConfig(agent_name="my-bot")
        assert cfg.agent_name == "my-bot"

    def test_disabled_telemetry(self) -> None:
        cfg = AgentConfig(telemetry_enabled=False)
        assert cfg.telemetry_enabled is False

    def test_plugins_list_stored(self) -> None:
        cfg = AgentConfig(plugins=["plugin-a", "plugin-b"])
        assert cfg.plugins == ["plugin-a", "plugin-b"]

    def test_custom_settings_stored(self) -> None:
        settings: dict[str, object] = {"timeout": 30, "retries": 3}
        cfg = AgentConfig(custom_settings=settings)
        assert cfg.custom_settings == settings


# ---------------------------------------------------------------------------
# from_yaml
# ---------------------------------------------------------------------------


class TestAgentConfigFromYaml:
    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent(
            """\
            agent_name: yaml-agent
            agent_version: "1.2.3"
            framework: langchain
            model: gpt-4o
            telemetry_enabled: false
            cost_tracking_enabled: true
            event_bus_enabled: true
            plugins:
              - plugin-x
            custom_settings:
              timeout: 60
            """
        )
        config_file = tmp_path / "agentcore.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        cfg = AgentConfig.from_yaml(config_file)
        assert cfg.agent_name == "yaml-agent"
        assert cfg.agent_version == "1.2.3"
        assert cfg.framework == "langchain"
        assert cfg.model == "gpt-4o"
        assert cfg.telemetry_enabled is False
        assert cfg.plugins == ["plugin-x"]

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.yaml"
        with pytest.raises(FileNotFoundError):
            AgentConfig.from_yaml(missing)

    def test_partial_yaml_uses_defaults_for_omitted_fields(
        self, tmp_path: Path
    ) -> None:
        yaml_content = "agent_name: partial-agent\n"
        config_file = tmp_path / "partial.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        cfg = AgentConfig.from_yaml(config_file)
        assert cfg.agent_name == "partial-agent"
        assert cfg.framework == "custom"  # default

    def test_accepts_path_string(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agentcore.yaml"
        config_file.write_text("agent_name: str-path\n", encoding="utf-8")
        cfg = AgentConfig.from_yaml(str(config_file))
        assert cfg.agent_name == "str-path"


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------


class TestAgentConfigFromEnv:
    def test_reads_agent_name_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTCORE_AGENT_NAME", "env-agent")
        cfg = AgentConfig.from_env()
        assert cfg.agent_name == "env-agent"

    def test_bool_true_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for truthy in ["true", "1", "yes"]:
            monkeypatch.setenv("AGENTCORE_TELEMETRY_ENABLED", truthy)
            cfg = AgentConfig.from_env()
            assert cfg.telemetry_enabled is True

    def test_bool_false_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTCORE_COST_TRACKING_ENABLED", "false")
        cfg = AgentConfig.from_env()
        assert cfg.cost_tracking_enabled is False

    def test_plugins_comma_separated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTCORE_PLUGINS", "alpha,beta,gamma")
        cfg = AgentConfig.from_env()
        assert cfg.plugins == ["alpha", "beta", "gamma"]

    def test_plugins_with_spaces_stripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENTCORE_PLUGINS", " alpha , beta ")
        cfg = AgentConfig.from_env()
        assert cfg.plugins == ["alpha", "beta"]

    def test_custom_settings_parsed_as_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENTCORE_CUSTOM_SETTINGS", '{"timeout": 30}')
        cfg = AgentConfig.from_env()
        assert cfg.custom_settings == {"timeout": 30}

    def test_invalid_custom_settings_json_defaults_to_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENTCORE_CUSTOM_SETTINGS", "not-json{{")
        cfg = AgentConfig.from_env()
        assert cfg.custom_settings == {}

    def test_non_prefixed_env_vars_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UNRELATED_VAR", "should-be-ignored")
        cfg = AgentConfig.from_env()
        assert cfg.agent_name == "unnamed-agent"

    def test_custom_prefix_respected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP_AGENT_NAME", "custom-prefix-agent")
        cfg = AgentConfig.from_env(prefix="MYAPP_")
        assert cfg.agent_name == "custom-prefix-agent"


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


class TestAgentConfigMerge:
    def test_non_default_override_wins(self) -> None:
        base = AgentConfig(agent_name="base-agent")
        override = AgentConfig(agent_name="override-agent")
        merged = base.merge(override)
        assert merged.agent_name == "override-agent"

    def test_base_field_retained_when_override_is_default(self) -> None:
        base = AgentConfig(agent_name="base-agent")
        override = AgentConfig()  # all defaults — should not override
        merged = base.merge(override)
        assert merged.agent_name == "base-agent"

    def test_plugins_are_unioned_not_replaced(self) -> None:
        base = AgentConfig(plugins=["alpha"])
        override = AgentConfig(plugins=["beta"])
        merged = base.merge(override)
        assert "alpha" in merged.plugins
        assert "beta" in merged.plugins

    def test_plugins_deduplication_on_merge(self) -> None:
        base = AgentConfig(plugins=["alpha", "beta"])
        override = AgentConfig(plugins=["beta", "gamma"])
        merged = base.merge(override)
        assert merged.plugins.count("beta") == 1

    def test_custom_settings_merged_shallowly(self) -> None:
        base = AgentConfig(custom_settings={"a": 1, "b": 2})
        override = AgentConfig(custom_settings={"b": 99, "c": 3})
        merged = base.merge(override)
        assert merged.custom_settings["a"] == 1
        assert merged.custom_settings["b"] == 99
        assert merged.custom_settings["c"] == 3

    def test_merge_does_not_mutate_self(self) -> None:
        base = AgentConfig(agent_name="base-agent")
        override = AgentConfig(agent_name="new-agent")
        base.merge(override)
        assert base.agent_name == "base-agent"

    def test_merge_does_not_mutate_overrides(self) -> None:
        base = AgentConfig(plugins=["a"])
        override = AgentConfig(plugins=["b"])
        base.merge(override)
        assert override.plugins == ["b"]
