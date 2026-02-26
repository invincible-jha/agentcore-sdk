"""Agent identity factory helpers for agentcore-sdk.

Re-exports ``AgentIdentity`` from the schema module so that consumers can
import it from either location, and provides a convenience factory function.

Shipped in this module
----------------------
- AgentIdentity       — re-export of the canonical dataclass
- create_identity()   — ergonomic factory with sensible defaults

Withheld / internal
-------------------
Cross-tenant identity minting, hardware-attested identities, and signed
identity tokens are available via plugins.
"""
from __future__ import annotations

from agentcore.schema.identity import AgentIdentity

__all__ = ["AgentIdentity", "create_identity"]


def create_identity(
    name: str,
    version: str = "0.1.0",
    framework: str = "custom",
    model: str = "claude-sonnet-4-5",
    metadata: dict[str, object] | None = None,
) -> AgentIdentity:
    """Create a new :class:`AgentIdentity` with a freshly generated UUID.

    Parameters
    ----------
    name:
        Human-readable agent name, e.g. ``"research-agent"``.
    version:
        SemVer string for the agent release.  Defaults to ``"0.1.0"``.
    framework:
        Agent framework identifier.  Defaults to ``"custom"``.
    model:
        Primary LLM identifier.  Defaults to ``"claude-sonnet-4-5"``.
    metadata:
        Optional key/value tags — environment, team, region, etc.

    Returns
    -------
    AgentIdentity
        A fully populated identity with an auto-generated ``agent_id`` and
        ``created_at`` set to the current UTC time.

    Examples
    --------
    >>> identity = create_identity("my-bot", version="1.0.0", framework="crewai")
    >>> identity.name
    'my-bot'
    >>> len(identity.fingerprint()) == 64
    True
    """
    return AgentIdentity(
        name=name,
        version=version,
        framework=framework,
        model=model,
        metadata=metadata or {},
    )
