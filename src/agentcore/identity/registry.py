"""Agent identity registry for agentcore-sdk.

The ``AgentRegistry`` provides a thread-safe in-memory store of
``AgentIdentity`` objects so that any component in the agent system can
resolve an agent ID to its full identity without going back to the source.

Shipped in this module
----------------------
- AgentRegistry   — thread-safe CRUD registry for AgentIdentity objects

Withheld / internal
-------------------
Distributed registry backends (Redis, etcd, Consul), TTL-based expiry, and
cross-datacenter replication are available via plugins.
"""
from __future__ import annotations

import threading

from agentcore.schema.errors import IdentityError
from agentcore.schema.identity import AgentIdentity


class AgentRegistry:
    """Thread-safe in-memory registry for :class:`~agentcore.schema.identity.AgentIdentity` objects.

    All read and write operations acquire the internal lock to guarantee
    consistent views across threads.

    Examples
    --------
    >>> registry = AgentRegistry()
    >>> from agentcore.identity.agent_id import create_identity
    >>> identity = create_identity("worker-1")
    >>> registry.register(identity)
    >>> registry.get(identity.agent_id).name
    'worker-1'
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, AgentIdentity] = {}

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def register(self, identity: AgentIdentity) -> None:
        """Add *identity* to the registry.

        Parameters
        ----------
        identity:
            The identity to register.

        Raises
        ------
        IdentityError
            If an identity with the same ``agent_id`` is already registered.
        """
        with self._lock:
            if identity.agent_id in self._store:
                raise IdentityError(
                    f"Identity {identity.agent_id!r} is already registered. "
                    "Call unregister() first or use a different agent_id.",
                    context={"agent_id": identity.agent_id},
                )
            self._store[identity.agent_id] = identity

    def unregister(self, agent_id: str) -> None:
        """Remove the identity associated with *agent_id*.

        Parameters
        ----------
        agent_id:
            The UUID string of the agent to deregister.

        Raises
        ------
        IdentityError
            If *agent_id* is not currently registered.
        """
        with self._lock:
            if agent_id not in self._store:
                raise IdentityError(
                    f"Agent {agent_id!r} is not registered.",
                    context={"agent_id": agent_id},
                )
            del self._store[agent_id]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> AgentIdentity:
        """Return the identity for *agent_id*.

        Parameters
        ----------
        agent_id:
            The UUID string to look up.

        Returns
        -------
        AgentIdentity

        Raises
        ------
        IdentityError
            If *agent_id* is not registered.
        """
        with self._lock:
            if agent_id not in self._store:
                raise IdentityError(
                    f"Agent {agent_id!r} is not registered.",
                    context={"agent_id": agent_id},
                )
            return self._store[agent_id]

    def list_all(self) -> list[AgentIdentity]:
        """Return a snapshot list of all registered identities.

        Returns
        -------
        list[AgentIdentity]
            Identities in insertion order (CPython 3.7+ dict guarantee).
        """
        with self._lock:
            return list(self._store.values())

    def find_by_name(self, name: str) -> list[AgentIdentity]:
        """Return all identities whose ``name`` matches *name* exactly.

        Parameters
        ----------
        name:
            The agent name to search for.

        Returns
        -------
        list[AgentIdentity]
            May be empty if no agents carry that name.
        """
        with self._lock:
            return [ident for ident in self._store.values() if ident.name == name]

    def find_by_framework(self, framework: str) -> list[AgentIdentity]:
        """Return all identities whose ``framework`` matches *framework*.

        Parameters
        ----------
        framework:
            Framework identifier, e.g. ``"langchain"``.

        Returns
        -------
        list[AgentIdentity]
        """
        with self._lock:
            return [
                ident for ident in self._store.values() if ident.framework == framework
            ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of registered identities."""
        with self._lock:
            return len(self._store)

    def __contains__(self, agent_id: object) -> bool:
        """Support ``agent_id in registry`` membership test."""
        with self._lock:
            return agent_id in self._store

    def __repr__(self) -> str:
        return f"AgentRegistry(count={len(self)})"
