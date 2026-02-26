"""Unit tests for agentcore.config.loader and agentcore.config.schema."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from agentcore.config.loader import ConfigLoader, _AUTO_SEARCH_PATHS
from agentcore.config.schema import validate_config
from agentcore.schema.config import AgentConfig
from agentcore.schema.errors import ConfigurationError


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_valid_minimal_dict(self) -> None:
        config = validate_config({})
        assert isinstance(config, AgentConfig)

    def test_valid_dict_with_agent_name(self) -> None:
        config = validate_config({"agent_name": "test-agent"})
        assert config.agent_name == "test-agent"

    def test_invalid_data_raises_configuration_error(self) -> None:
        # plugins must be list[str]; passing a plain integer cannot be coerced
        with pytest.raises(ConfigurationError):
            validate_config({"plugins": 5})

    def test_configuration_error_has_cause(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config({"plugins": 5})
        assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# ConfigLoader.load_yaml
# ---------------------------------------------------------------------------

class TestConfigLoaderLoadYaml:
    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agentcore.yaml"
        config_file.write_text("agent_name: yaml-agent\n", encoding="utf-8")

        loader = ConfigLoader()
        config = loader.load_yaml(config_file)
        assert config.agent_name == "yaml-agent"

    def test_load_yaml_with_path_string(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agentcore.yaml"
        config_file.write_text("agent_name: str-path-agent\n", encoding="utf-8")

        loader = ConfigLoader()
        config = loader.load_yaml(str(config_file))
        assert config.agent_name == "str-path-agent"

    def test_missing_yaml_file_raises_configuration_error(self, tmp_path: Path) -> None:
        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_yaml(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises_configuration_error(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed\n", encoding="utf-8")
        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="parse"):
            loader.load_yaml(bad_yaml)

    def test_non_mapping_yaml_returns_defaults(self, tmp_path: Path) -> None:
        # A YAML file containing a list instead of a dict
        non_mapping = tmp_path / "list.yaml"
        non_mapping.write_text("- one\n- two\n", encoding="utf-8")
        loader = ConfigLoader()
        config = loader.load_yaml(non_mapping)
        # Falls back to empty dict -> default config
        assert isinstance(config, AgentConfig)


# ---------------------------------------------------------------------------
# ConfigLoader.load_json
# ---------------------------------------------------------------------------

class TestConfigLoaderLoadJson:
    def test_load_valid_json(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agentcore.json"
        config_file.write_text(json.dumps({"agent_name": "json-agent"}), encoding="utf-8")
        loader = ConfigLoader()
        config = loader.load_json(config_file)
        assert config.agent_name == "json-agent"

    def test_missing_json_file_raises_configuration_error(self, tmp_path: Path) -> None:
        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_json(Path("/nonexistent/path/file.json"))

    def test_invalid_json_raises_configuration_error(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{not valid json}", encoding="utf-8")
        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="parse"):
            loader.load_json(bad_json)

    def test_non_mapping_json_returns_defaults(self, tmp_path: Path) -> None:
        list_json = tmp_path / "list.json"
        list_json.write_text('["a", "b"]', encoding="utf-8")
        loader = ConfigLoader()
        config = loader.load_json(list_json)
        assert isinstance(config, AgentConfig)


# ---------------------------------------------------------------------------
# ConfigLoader.load_env
# ---------------------------------------------------------------------------

class TestConfigLoaderLoadEnv:
    def test_load_env_returns_agent_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENTCORE_AGENT_NAME", raising=False)
        loader = ConfigLoader()
        config = loader.load_env()
        assert isinstance(config, AgentConfig)

    def test_load_env_picks_up_agent_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTCORE_AGENT_NAME", "env-agent")
        loader = ConfigLoader()
        config = loader.load_env()
        assert config.agent_name == "env-agent"

    def test_load_env_custom_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP_AGENT_NAME", "prefix-agent")
        loader = ConfigLoader()
        config = loader.load_env(prefix="MYAPP_")
        assert config.agent_name == "prefix-agent"


# ---------------------------------------------------------------------------
# ConfigLoader.load_auto
# ---------------------------------------------------------------------------

class TestConfigLoaderLoadAuto:
    def test_load_auto_uses_default_config_when_no_file(self, tmp_path: Path) -> None:
        loader = ConfigLoader()
        config = loader.load_auto(search_dir=tmp_path)
        assert isinstance(config, AgentConfig)

    def test_load_auto_finds_yaml_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agentcore.yaml"
        config_file.write_text("agent_name: auto-yaml\n", encoding="utf-8")
        loader = ConfigLoader()
        config = loader.load_auto(search_dir=tmp_path)
        assert config.agent_name == "auto-yaml"

    def test_load_auto_finds_json_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agentcore.json"
        config_file.write_text(json.dumps({"agent_name": "auto-json"}), encoding="utf-8")
        loader = ConfigLoader()
        config = loader.load_auto(search_dir=tmp_path)
        assert config.agent_name == "auto-json"

    def test_load_auto_prefers_yaml_over_json(self, tmp_path: Path) -> None:
        # agentcore.yaml is earlier in _AUTO_SEARCH_PATHS than agentcore.json
        (tmp_path / "agentcore.yaml").write_text("agent_name: from-yaml\n", encoding="utf-8")
        (tmp_path / "agentcore.json").write_text(
            json.dumps({"agent_name": "from-json"}), encoding="utf-8"
        )
        loader = ConfigLoader()
        config = loader.load_auto(search_dir=tmp_path)
        assert config.agent_name == "from-yaml"

    def test_load_auto_overlays_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_file = tmp_path / "agentcore.yaml"
        config_file.write_text("agent_name: file-name\n", encoding="utf-8")
        monkeypatch.setenv("AGENTCORE_AGENT_NAME", "env-override")

        loader = ConfigLoader()
        config = loader.load_auto(search_dir=tmp_path)
        assert config.agent_name == "env-override"

    def test_load_auto_skips_bad_file_and_tries_next(self, tmp_path: Path) -> None:
        # Write an invalid YAML first, then a valid JSON fallback
        (tmp_path / "agentcore.yaml").write_text("key: [bad yaml", encoding="utf-8")
        (tmp_path / "agentcore.json").write_text(
            json.dumps({"agent_name": "fallback-json"}), encoding="utf-8"
        )
        loader = ConfigLoader()
        config = loader.load_auto(search_dir=tmp_path)
        assert config.agent_name == "fallback-json"

    def test_load_auto_hidden_yaml_variant(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".agentcore.yaml"
        config_file.write_text("agent_name: hidden-yaml\n", encoding="utf-8")
        loader = ConfigLoader()
        config = loader.load_auto(search_dir=tmp_path)
        assert config.agent_name == "hidden-yaml"
