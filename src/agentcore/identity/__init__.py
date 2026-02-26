"""Identity package for agentcore-sdk.

Provides agent identity creation, registry, and provider abstractions.
"""
from __future__ import annotations

from agentcore.identity.agent_id import AgentIdentity, create_identity
from agentcore.identity.provider import BasicIdentityProvider, IdentityProvider
from agentcore.identity.registry import AgentRegistry

__all__ = [
    "AgentIdentity",
    "create_identity",
    "AgentRegistry",
    "IdentityProvider",
    "BasicIdentityProvider",
]
