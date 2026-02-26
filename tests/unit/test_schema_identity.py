"""Unit tests for agentcore.schema.identity.

Tests cover AgentIdentity creation, serialisation round-trips,
fingerprinting determinism, and from_dict edge cases.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

import pytest

from agentcore.schema.identity import AgentIdentity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_identity() -> AgentIdentity:
    """AgentIdentity with only the four required fields."""
    return AgentIdentity(
        name="test-agent",
        version="1.0.0",
        framework="custom",
        model="claude-sonnet-4-5",
    )


@pytest.fixture()
def rich_identity() -> AgentIdentity:
    """AgentIdentity with metadata and an explicit agent_id."""
    return AgentIdentity(
        name="rich-agent",
        version="2.3.1",
        framework="langchain",
        model="gpt-4o",
        agent_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        metadata={"env": "prod", "team": "platform"},
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestAgentIdentityConstruction:
    def test_required_fields_are_stored(self, minimal_identity: AgentIdentity) -> None:
        assert minimal_identity.name == "test-agent"
        assert minimal_identity.version == "1.0.0"
        assert minimal_identity.framework == "custom"
        assert minimal_identity.model == "claude-sonnet-4-5"

    def test_agent_id_auto_generated_as_uuid4(
        self, minimal_identity: AgentIdentity
    ) -> None:
        parsed = uuid.UUID(minimal_identity.agent_id, version=4)
        assert str(parsed) == minimal_identity.agent_id

    def test_two_identities_get_different_agent_ids(self) -> None:
        a = AgentIdentity(name="a", version="1", framework="x", model="y")
        b = AgentIdentity(name="a", version="1", framework="x", model="y")
        assert a.agent_id != b.agent_id

    def test_created_at_is_utc_datetime(self, minimal_identity: AgentIdentity) -> None:
        assert isinstance(minimal_identity.created_at, datetime)
        assert minimal_identity.created_at.tzinfo is not None

    def test_metadata_defaults_to_empty_dict(
        self, minimal_identity: AgentIdentity
    ) -> None:
        assert minimal_identity.metadata == {}

    def test_explicit_metadata_stored(self, rich_identity: AgentIdentity) -> None:
        assert rich_identity.metadata == {"env": "prod", "team": "platform"}

    def test_explicit_agent_id_preserved(self, rich_identity: AgentIdentity) -> None:
        assert rich_identity.agent_id == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------


class TestAgentIdentityFingerprint:
    def test_fingerprint_returns_64_char_hex_string(
        self, minimal_identity: AgentIdentity
    ) -> None:
        fp = minimal_identity.fingerprint()
        assert isinstance(fp, str)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_same_stable_fields_produce_same_fingerprint(self) -> None:
        a = AgentIdentity(name="bot", version="1", framework="x", model="y")
        b = AgentIdentity(name="bot", version="1", framework="x", model="y")
        assert a.fingerprint() == b.fingerprint()

    def test_different_name_changes_fingerprint(self) -> None:
        a = AgentIdentity(name="bot-a", version="1", framework="x", model="y")
        b = AgentIdentity(name="bot-b", version="1", framework="x", model="y")
        assert a.fingerprint() != b.fingerprint()

    def test_different_version_changes_fingerprint(self) -> None:
        a = AgentIdentity(name="bot", version="1.0.0", framework="x", model="y")
        b = AgentIdentity(name="bot", version="2.0.0", framework="x", model="y")
        assert a.fingerprint() != b.fingerprint()

    def test_different_framework_changes_fingerprint(self) -> None:
        a = AgentIdentity(name="bot", version="1", framework="langchain", model="y")
        b = AgentIdentity(name="bot", version="1", framework="crewai", model="y")
        assert a.fingerprint() != b.fingerprint()

    def test_different_model_changes_fingerprint(self) -> None:
        a = AgentIdentity(name="bot", version="1", framework="x", model="gpt-4o")
        b = AgentIdentity(name="bot", version="1", framework="x", model="claude-opus-4")
        assert a.fingerprint() != b.fingerprint()

    def test_metadata_does_not_affect_fingerprint(self) -> None:
        a = AgentIdentity(
            name="bot", version="1", framework="x", model="y", metadata={}
        )
        b = AgentIdentity(
            name="bot",
            version="1",
            framework="x",
            model="y",
            metadata={"extra": "value"},
        )
        assert a.fingerprint() == b.fingerprint()

    def test_agent_id_does_not_affect_fingerprint(self) -> None:
        fixed_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        a = AgentIdentity(
            name="bot", version="1", framework="x", model="y", agent_id=fixed_id
        )
        b = AgentIdentity(
            name="bot", version="1", framework="x", model="y", agent_id=other_id
        )
        assert a.fingerprint() == b.fingerprint()

    def test_fingerprint_matches_manual_sha256(
        self, minimal_identity: AgentIdentity
    ) -> None:
        stable = {
            "framework": minimal_identity.framework,
            "model": minimal_identity.model,
            "name": minimal_identity.name,
            "version": minimal_identity.version,
        }
        canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        assert minimal_identity.fingerprint() == expected


# ---------------------------------------------------------------------------
# Serialisation (to_dict / from_dict)
# ---------------------------------------------------------------------------


class TestAgentIdentitySerialisation:
    def test_to_dict_contains_all_keys(self, minimal_identity: AgentIdentity) -> None:
        d = minimal_identity.to_dict()
        assert set(d.keys()) == {
            "agent_id",
            "name",
            "version",
            "framework",
            "model",
            "created_at",
            "metadata",
        }

    def test_to_dict_created_at_is_iso8601_string(
        self, minimal_identity: AgentIdentity
    ) -> None:
        d = minimal_identity.to_dict()
        raw_ts = d["created_at"]
        assert isinstance(raw_ts, str)
        # Must parse without raising
        datetime.fromisoformat(raw_ts)

    def test_round_trip_via_dict(self, minimal_identity: AgentIdentity) -> None:
        restored = AgentIdentity.from_dict(minimal_identity.to_dict())
        assert restored.name == minimal_identity.name
        assert restored.version == minimal_identity.version
        assert restored.framework == minimal_identity.framework
        assert restored.model == minimal_identity.model
        assert restored.agent_id == minimal_identity.agent_id

    def test_round_trip_preserves_metadata(self, rich_identity: AgentIdentity) -> None:
        restored = AgentIdentity.from_dict(rich_identity.to_dict())
        assert restored.metadata == rich_identity.metadata

    def test_from_dict_generates_agent_id_when_absent(self) -> None:
        payload: dict[str, object] = {
            "name": "anon",
            "version": "0",
            "framework": "custom",
            "model": "gpt-4o-mini",
        }
        identity = AgentIdentity.from_dict(payload)
        # Must be a valid UUID4
        parsed = uuid.UUID(identity.agent_id, version=4)
        assert str(parsed) == identity.agent_id

    def test_from_dict_accepts_datetime_object_for_created_at(self) -> None:
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload: dict[str, object] = {
            "name": "dt-agent",
            "version": "1",
            "framework": "custom",
            "model": "gpt-4o",
            "created_at": ts,
        }
        identity = AgentIdentity.from_dict(payload)
        assert identity.created_at == ts

    def test_from_dict_missing_required_field_raises_key_error(self) -> None:
        payload: dict[str, object] = {
            "name": "no-model",
            "version": "1",
            "framework": "custom",
            # "model" is intentionally omitted
        }
        with pytest.raises(KeyError):
            AgentIdentity.from_dict(payload)

    def test_from_dict_non_dict_metadata_defaults_to_empty(self) -> None:
        payload: dict[str, object] = {
            "name": "m",
            "version": "1",
            "framework": "custom",
            "model": "gpt-4o",
            "metadata": "not-a-dict",
        }
        identity = AgentIdentity.from_dict(payload)
        assert identity.metadata == {}
