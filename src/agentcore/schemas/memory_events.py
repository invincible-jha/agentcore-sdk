"""Memory event schemas — read, write, delete.

Memory events are emitted when an agent interacts with its long-term or
working-memory store.  They provide an audit trail of all memory operations
without exposing the actual stored values (which may be sensitive).

All models are frozen Pydantic BaseModels.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# MemoryReadEvent
# ---------------------------------------------------------------------------


class MemoryReadEvent(BaseModel):
    """Emitted when an agent reads one or more items from its memory store.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the read was performed.
    agent_id:
        Identifier of the agent performing the read.
    event_type:
        Always ``"memory_read"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    memory_key:
        The primary key or namespace queried.
    memory_scope:
        Logical scope of the memory store (e.g. ``"session"``, ``"user"``,
        ``"global"``).
    items_returned:
        Number of items the read operation returned.
    query_summary:
        Brief description of the query or retrieval criteria.
    cache_hit:
        Whether the result came from a cache rather than the backing store.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["memory_read"] = "memory_read"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    memory_key: str = ""
    memory_scope: str = "session"
    items_returned: int = 0
    query_summary: str = ""
    cache_hit: bool = False


# ---------------------------------------------------------------------------
# MemoryWriteEvent
# ---------------------------------------------------------------------------


class MemoryWriteEvent(BaseModel):
    """Emitted when an agent writes or updates items in its memory store.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the write was performed.
    agent_id:
        Identifier of the agent performing the write.
    event_type:
        Always ``"memory_write"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    memory_key:
        The primary key or namespace written to.
    memory_scope:
        Logical scope of the memory store.
    operation:
        Write operation type: ``"insert"``, ``"update"``, or ``"upsert"``.
    items_written:
        Number of items affected by the write.
    size_bytes:
        Approximate size of the written payload in bytes.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["memory_write"] = "memory_write"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    memory_key: str = ""
    memory_scope: str = "session"
    operation: Literal["insert", "update", "upsert"] = "upsert"
    items_written: int = 0
    size_bytes: int = 0


# ---------------------------------------------------------------------------
# MemoryDeletedEvent
# ---------------------------------------------------------------------------


class MemoryDeletedEvent(BaseModel):
    """Emitted when an agent deletes items from its memory store.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the deletion was performed.
    agent_id:
        Identifier of the agent performing the deletion.
    event_type:
        Always ``"memory_deleted"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    memory_key:
        The primary key or namespace deleted.
    memory_scope:
        Logical scope of the memory store.
    items_deleted:
        Number of items removed by the operation.
    deletion_reason:
        Optional explanation for why the data was deleted (e.g. TTL expiry,
        user request, policy enforcement).
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["memory_deleted"] = "memory_deleted"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    memory_key: str = ""
    memory_scope: str = "session"
    items_deleted: int = 0
    deletion_reason: str = ""
