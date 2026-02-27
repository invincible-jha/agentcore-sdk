"""Delegation event schemas — sent, received, completed.

Delegation events capture the lifecycle of cross-agent task delegation.
When an orchestrator agent delegates a subtask to a worker agent, three events
are emitted: DelegationSentEvent (by the orchestrator), DelegationReceivedEvent
(by the worker), and DelegationCompletedEvent (by the worker upon finish).

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
# DelegationSentEvent
# ---------------------------------------------------------------------------


class DelegationSentEvent(BaseModel):
    """Emitted by an orchestrator agent when it sends a task to a worker.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the delegation was dispatched.
    agent_id:
        Identifier of the orchestrator agent sending the task.
    event_type:
        Always ``"delegation_sent"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    delegation_id:
        Unique identifier for this delegation; correlates all three events
        in the delegation lifecycle.
    target_agent_id:
        Identifier of the worker agent receiving the task.
    task_summary:
        Brief human-readable description of the delegated task.
    priority:
        Integer priority where 1 is highest and 10 is lowest.
    deadline_iso:
        Optional ISO 8601 UTC deadline string for task completion.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["delegation_sent"] = "delegation_sent"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    delegation_id: str = Field(default_factory=_new_uuid)
    target_agent_id: str = ""
    task_summary: str = ""
    priority: int = 5
    deadline_iso: str = ""


# ---------------------------------------------------------------------------
# DelegationReceivedEvent
# ---------------------------------------------------------------------------


class DelegationReceivedEvent(BaseModel):
    """Emitted by a worker agent when it accepts a delegated task.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the task was accepted.
    agent_id:
        Identifier of the worker agent receiving the task.
    event_type:
        Always ``"delegation_received"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    delegation_id:
        Matches the ``delegation_id`` from ``DelegationSentEvent``.
    source_agent_id:
        Identifier of the orchestrator that sent the task.
    task_summary:
        Brief human-readable description of the received task.
    accepted:
        Whether the worker accepted (True) or rejected (False) the task.
    rejection_reason:
        Explanation when ``accepted`` is False.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["delegation_received"] = "delegation_received"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    delegation_id: str = ""
    source_agent_id: str = ""
    task_summary: str = ""
    accepted: bool = True
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# DelegationCompletedEvent
# ---------------------------------------------------------------------------


class DelegationCompletedEvent(BaseModel):
    """Emitted by a worker agent when a delegated task finishes (success or failure).

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the task completed.
    agent_id:
        Identifier of the worker agent that executed the task.
    event_type:
        Always ``"delegation_completed"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    delegation_id:
        Matches the ``delegation_id`` from ``DelegationSentEvent``.
    source_agent_id:
        Identifier of the orchestrator that sent the task.
    success:
        Whether the delegated task completed successfully.
    result_summary:
        Brief human-readable description of the outcome.
    error_message:
        Populated when ``success`` is False.
    duration_ms:
        Wall-clock time to complete the task in milliseconds.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["delegation_completed"] = "delegation_completed"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    delegation_id: str = ""
    source_agent_id: str = ""
    success: bool = True
    result_summary: str = ""
    error_message: str = ""
    duration_ms: float = 0.0
