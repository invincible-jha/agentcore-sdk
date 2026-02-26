"""Identity provider abstractions for agentcore-sdk.

An ``IdentityProvider`` is a pluggable strategy for creating, verifying,
and rotating ``AgentIdentity`` objects.  The default ``BasicIdentityProvider``
is suitable for single-process or development use.

Shipped in this module
----------------------
- IdentityProvider        — ABC defining the provider contract
- BasicIdentityProvider   — in-memory implementation for dev / single-process

Withheld / internal
-------------------
PKI-backed identity providers, OAuth-integrated agents, hardware-attested
identities, and zero-trust rotation protocols are available via plugins.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from agentcore.schema.errors import IdentityError
from agentcore.schema.identity import AgentIdentity


class IdentityProvider(ABC):
    """Abstract base class for identity lifecycle management.

    Implementors are responsible for the full lifecycle of agent identities:
    creation, verification (is this identity authentic?), and rotation
    (issue a fresh identity while retiring the old one).
    """

    @abstractmethod
    def create_identity(
        self,
        name: str,
        version: str,
        framework: str,
        model: str,
        metadata: dict[str, object] | None = None,
    ) -> AgentIdentity:
        """Mint a new :class:`AgentIdentity`.

        Parameters
        ----------
        name, version, framework, model:
            Core identity fields.
        metadata:
            Optional tags.

        Returns
        -------
        AgentIdentity
        """

    @abstractmethod
    def verify_identity(self, identity: AgentIdentity) -> bool:
        """Return ``True`` if *identity* is considered authentic.

        Parameters
        ----------
        identity:
            The identity to verify.

        Returns
        -------
        bool
        """

    @abstractmethod
    def rotate_identity(self, identity: AgentIdentity) -> AgentIdentity:
        """Issue a new identity that supersedes *identity*.

        The new identity carries a fresh ``agent_id`` but preserves the
        stable fields (name, version, framework, model).

        Parameters
        ----------
        identity:
            The identity to rotate.

        Returns
        -------
        AgentIdentity
            The replacement identity.
        """


class BasicIdentityProvider(IdentityProvider):
    """Simple in-memory identity provider.

    Suitable for development, testing, and single-process deployments.
    Verification is performed by checking that the provided identity's
    ``agent_id`` is a well-formed UUID4.

    Examples
    --------
    >>> provider = BasicIdentityProvider()
    >>> identity = provider.create_identity(
    ...     "bot", "1.0.0", "custom", "gpt-4o"
    ... )
    >>> provider.verify_identity(identity)
    True
    """

    def create_identity(
        self,
        name: str,
        version: str,
        framework: str,
        model: str,
        metadata: dict[str, object] | None = None,
    ) -> AgentIdentity:
        """Create a new identity with a freshly generated UUID4 agent_id."""
        return AgentIdentity(
            name=name,
            version=version,
            framework=framework,
            model=model,
            metadata=metadata or {},
        )

    def verify_identity(self, identity: AgentIdentity) -> bool:
        """Return ``True`` if the identity's ``agent_id`` is a valid UUID4.

        Parameters
        ----------
        identity:
            Identity to check.

        Returns
        -------
        bool
        """
        try:
            parsed = uuid.UUID(identity.agent_id, version=4)
            return str(parsed) == identity.agent_id
        except (ValueError, AttributeError):
            return False

    def rotate_identity(self, identity: AgentIdentity) -> AgentIdentity:
        """Return a new identity with the same stable fields and a fresh UUID.

        Parameters
        ----------
        identity:
            The identity to rotate.

        Returns
        -------
        AgentIdentity
            Fresh identity.

        Raises
        ------
        IdentityError
            If the original identity fails verification.
        """
        if not self.verify_identity(identity):
            raise IdentityError(
                f"Cannot rotate unverified identity {identity.agent_id!r}.",
                context={"agent_id": identity.agent_id},
            )
        return AgentIdentity(
            name=identity.name,
            version=identity.version,
            framework=identity.framework,
            model=identity.model,
            metadata=dict(identity.metadata),
        )
