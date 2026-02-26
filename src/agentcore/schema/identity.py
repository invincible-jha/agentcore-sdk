"""Agent identity schema for agentcore-sdk.

This module is part of the *public* schema surface and defines the canonical
representation of an agent's stable identity — who an agent *is*, independent
of what it is doing.

Shipped in this module
----------------------
- AgentIdentity   — dataclass capturing all stable identity fields
- fingerprint()   — deterministic SHA-256 identity hash

Withheld / internal
-------------------
Identity attestation, cross-tenant federation, and cryptographic signing of
identities are not part of this open-source SDK and are available via plugins.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AgentIdentity:
    """Stable, serialisable identity for an agent.

    Parameters
    ----------
    agent_id:
        Globally unique identifier (UUID4 string).  Auto-generated when
        not supplied.
    name:
        Human-readable agent name, e.g. ``"research-agent-v2"``.
    version:
        SemVer string representing the agent's release, e.g. ``"1.0.0"``.
    framework:
        The agent framework in use, e.g. ``"langchain"``, ``"crewai"``,
        ``"custom"``.
    model:
        The primary language model identifier, e.g.
        ``"claude-sonnet-4-5"``.
    created_at:
        UTC creation timestamp; auto-set to *now* when not provided.
    metadata:
        Arbitrary key/value tags — environment, owner, team, etc.

    Examples
    --------
    >>> identity = AgentIdentity(name="my-agent", version="1.0.0",
    ...                          framework="custom", model="gpt-4o")
    >>> len(identity.fingerprint()) == 64
    True
    """

    # Stable identity fields — changes to these change the fingerprint
    name: str
    version: str
    framework: str
    model: str

    # Auto-generated / mutable fields
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, object] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Serialise identity to a plain dict.

        Returns
        -------
        dict[str, object]
            All fields.  ``created_at`` is ISO-8601.
        """
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "framework": self.framework,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AgentIdentity":
        """Reconstruct an ``AgentIdentity`` from a serialised dict.

        Parameters
        ----------
        payload:
            A dict produced by :meth:`to_dict` or with compatible keys.

        Returns
        -------
        AgentIdentity

        Raises
        ------
        KeyError
            If required fields are absent from ``payload``.
        """
        raw_ts = payload.get("created_at")
        if isinstance(raw_ts, str):
            created_at = datetime.fromisoformat(raw_ts)
        elif isinstance(raw_ts, datetime):
            created_at = raw_ts
        else:
            created_at = datetime.now(tz=timezone.utc)

        raw_meta = payload.get("metadata", {})
        metadata: dict[str, object] = dict(raw_meta) if isinstance(raw_meta, dict) else {}

        raw_id = payload.get("agent_id")
        agent_id = str(raw_id) if raw_id is not None else str(uuid.uuid4())

        return cls(
            agent_id=agent_id,
            name=str(payload["name"]),
            version=str(payload["version"]),
            framework=str(payload["framework"]),
            model=str(payload["model"]),
            created_at=created_at,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Fingerprinting
    # ------------------------------------------------------------------

    def fingerprint(self) -> str:
        """Return a deterministic SHA-256 hash of the stable identity fields.

        The hash is computed over ``name``, ``version``, ``framework``, and
        ``model`` in a canonical JSON representation.  It is *not* sensitive
        to ``agent_id``, ``created_at``, or ``metadata`` so that two agents
        with the same logical identity produce the same fingerprint regardless
        of when they were created.

        Returns
        -------
        str
            Lower-case hexadecimal SHA-256 digest (64 characters).

        Examples
        --------
        >>> a = AgentIdentity(name="bot", version="1", framework="x", model="y")
        >>> b = AgentIdentity(name="bot", version="1", framework="x", model="y")
        >>> a.fingerprint() == b.fingerprint()
        True
        """
        stable: dict[str, str] = {
            "name": self.name,
            "version": self.version,
            "framework": self.framework,
            "model": self.model,
        }
        # Sort keys for determinism; use separators to minimise bytes
        canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
