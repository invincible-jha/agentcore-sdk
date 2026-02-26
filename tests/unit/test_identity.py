"""Unit tests for agentcore.identity (agent_id, registry, provider).

Tests cover create_identity factory, AgentRegistry CRUD, and
BasicIdentityProvider lifecycle methods.
"""
from __future__ import annotations

import uuid

import pytest

from agentcore.identity.agent_id import AgentIdentity, create_identity
from agentcore.identity.provider import BasicIdentityProvider
from agentcore.identity.registry import AgentRegistry
from agentcore.schema.errors import IdentityError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> AgentRegistry:
    return AgentRegistry()


@pytest.fixture()
def provider() -> BasicIdentityProvider:
    return BasicIdentityProvider()


@pytest.fixture()
def sample_identity() -> AgentIdentity:
    return create_identity(
        name="sample-agent",
        version="1.0.0",
        framework="langchain",
        model="gpt-4o",
    )


# ---------------------------------------------------------------------------
# create_identity factory
# ---------------------------------------------------------------------------


class TestCreateIdentity:
    def test_name_is_stored(self) -> None:
        identity = create_identity("my-agent")
        assert identity.name == "my-agent"

    def test_default_version(self) -> None:
        identity = create_identity("a")
        assert identity.version == "0.1.0"

    def test_default_framework(self) -> None:
        identity = create_identity("a")
        assert identity.framework == "custom"

    def test_default_model(self) -> None:
        identity = create_identity("a")
        assert identity.model == "claude-sonnet-4-5"

    def test_explicit_version_stored(self) -> None:
        identity = create_identity("a", version="2.0.0")
        assert identity.version == "2.0.0"

    def test_explicit_framework_stored(self) -> None:
        identity = create_identity("a", framework="crewai")
        assert identity.framework == "crewai"

    def test_metadata_stored(self) -> None:
        identity = create_identity("a", metadata={"env": "test"})
        assert identity.metadata == {"env": "test"}

    def test_metadata_defaults_to_empty_dict(self) -> None:
        identity = create_identity("a")
        assert identity.metadata == {}

    def test_agent_id_is_valid_uuid4(self) -> None:
        identity = create_identity("a")
        parsed = uuid.UUID(identity.agent_id, version=4)
        assert str(parsed) == identity.agent_id

    def test_fingerprint_is_64_chars(self) -> None:
        identity = create_identity("a", version="1", framework="x", model="y")
        assert len(identity.fingerprint()) == 64


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------


class TestAgentRegistry:
    def test_register_and_get(
        self, registry: AgentRegistry, sample_identity: AgentIdentity
    ) -> None:
        registry.register(sample_identity)
        retrieved = registry.get(sample_identity.agent_id)
        assert retrieved.agent_id == sample_identity.agent_id
        assert retrieved.name == sample_identity.name

    def test_len_increments_after_register(
        self, registry: AgentRegistry, sample_identity: AgentIdentity
    ) -> None:
        assert len(registry) == 0
        registry.register(sample_identity)
        assert len(registry) == 1

    def test_contains_operator_true(
        self, registry: AgentRegistry, sample_identity: AgentIdentity
    ) -> None:
        registry.register(sample_identity)
        assert sample_identity.agent_id in registry

    def test_contains_operator_false_for_unregistered(
        self, registry: AgentRegistry
    ) -> None:
        assert "does-not-exist" not in registry

    def test_duplicate_registration_raises_identity_error(
        self, registry: AgentRegistry, sample_identity: AgentIdentity
    ) -> None:
        registry.register(sample_identity)
        with pytest.raises(IdentityError):
            registry.register(sample_identity)

    def test_get_unknown_agent_raises_identity_error(
        self, registry: AgentRegistry
    ) -> None:
        with pytest.raises(IdentityError):
            registry.get("unknown-id")

    def test_unregister_removes_identity(
        self, registry: AgentRegistry, sample_identity: AgentIdentity
    ) -> None:
        registry.register(sample_identity)
        registry.unregister(sample_identity.agent_id)
        assert sample_identity.agent_id not in registry

    def test_unregister_unknown_agent_raises_identity_error(
        self, registry: AgentRegistry
    ) -> None:
        with pytest.raises(IdentityError):
            registry.unregister("ghost-id")

    def test_list_all_returns_all_identities(self, registry: AgentRegistry) -> None:
        identity_a = create_identity("agent-a")
        identity_b = create_identity("agent-b")
        registry.register(identity_a)
        registry.register(identity_b)
        all_ids = {i.agent_id for i in registry.list_all()}
        assert identity_a.agent_id in all_ids
        assert identity_b.agent_id in all_ids

    def test_list_all_empty_when_no_registrations(
        self, registry: AgentRegistry
    ) -> None:
        assert registry.list_all() == []

    def test_find_by_name_returns_matching(self, registry: AgentRegistry) -> None:
        ia = create_identity("worker")
        ib = create_identity("worker")
        ic = create_identity("manager")
        registry.register(ia)
        registry.register(ib)
        registry.register(ic)
        workers = registry.find_by_name("worker")
        assert len(workers) == 2
        assert all(w.name == "worker" for w in workers)

    def test_find_by_name_empty_when_no_match(self, registry: AgentRegistry) -> None:
        registry.register(create_identity("agent-x"))
        assert registry.find_by_name("nonexistent") == []

    def test_find_by_framework_returns_matching(self, registry: AgentRegistry) -> None:
        lc_agent = create_identity("lc", framework="langchain")
        ca_agent = create_identity("ca", framework="crewai")
        registry.register(lc_agent)
        registry.register(ca_agent)
        langchain_agents = registry.find_by_framework("langchain")
        assert len(langchain_agents) == 1
        assert langchain_agents[0].framework == "langchain"

    def test_repr_contains_count(self, registry: AgentRegistry) -> None:
        registry.register(create_identity("x"))
        assert "1" in repr(registry)


# ---------------------------------------------------------------------------
# BasicIdentityProvider
# ---------------------------------------------------------------------------


class TestBasicIdentityProvider:
    def test_create_identity_stores_fields(
        self, provider: BasicIdentityProvider
    ) -> None:
        identity = provider.create_identity(
            name="bot", version="1.0.0", framework="crewai", model="gpt-4o"
        )
        assert identity.name == "bot"
        assert identity.version == "1.0.0"
        assert identity.framework == "crewai"
        assert identity.model == "gpt-4o"

    def test_create_identity_generates_uuid4(
        self, provider: BasicIdentityProvider
    ) -> None:
        identity = provider.create_identity("bot", "1", "x", "y")
        parsed = uuid.UUID(identity.agent_id, version=4)
        assert str(parsed) == identity.agent_id

    def test_create_identity_metadata_stored(
        self, provider: BasicIdentityProvider
    ) -> None:
        identity = provider.create_identity(
            "bot", "1", "x", "y", metadata={"team": "platform"}
        )
        assert identity.metadata == {"team": "platform"}

    def test_verify_identity_true_for_valid_uuid4(
        self, provider: BasicIdentityProvider
    ) -> None:
        identity = provider.create_identity("bot", "1", "x", "y")
        assert provider.verify_identity(identity) is True

    def test_verify_identity_false_for_invalid_agent_id(
        self, provider: BasicIdentityProvider
    ) -> None:
        identity = create_identity("bot")
        # Tamper with the agent_id
        object.__setattr__(identity, "agent_id", "not-a-uuid")
        assert provider.verify_identity(identity) is False

    def test_rotate_identity_produces_new_uuid(
        self, provider: BasicIdentityProvider
    ) -> None:
        original = provider.create_identity("bot", "1", "x", "y")
        rotated = provider.rotate_identity(original)
        assert rotated.agent_id != original.agent_id

    def test_rotate_identity_preserves_stable_fields(
        self, provider: BasicIdentityProvider
    ) -> None:
        original = provider.create_identity("bot", "1.0.0", "crewai", "gpt-4o")
        rotated = provider.rotate_identity(original)
        assert rotated.name == "bot"
        assert rotated.version == "1.0.0"
        assert rotated.framework == "crewai"
        assert rotated.model == "gpt-4o"

    def test_rotate_preserves_fingerprint(
        self, provider: BasicIdentityProvider
    ) -> None:
        original = provider.create_identity("bot", "1", "x", "y")
        rotated = provider.rotate_identity(original)
        assert original.fingerprint() == rotated.fingerprint()

    def test_rotate_invalid_identity_raises_identity_error(
        self, provider: BasicIdentityProvider
    ) -> None:
        identity = create_identity("bot")
        object.__setattr__(identity, "agent_id", "not-a-uuid")
        with pytest.raises(IdentityError):
            provider.rotate_identity(identity)
