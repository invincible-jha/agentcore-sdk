"""Lifecycle event schemas — agent start, complete, fail, pause, resume.

Every model is a frozen Pydantic BaseModel so instances are immutable and
hashable.  The ``event_type`` field is a string Literal so that consumers can
perform exhaustive pattern matching without pulling in the wider EventType enum.

Common base fields present on all events
-----------------------------------------
event_id   : UUID4 string, auto-generated.
timestamp  : UTC datetime, auto-set to *now* at construction time.
agent_id   : Stable identifier of the emitting agent.
event_type : String literal that uniquely names this event class.
aep_version: Agent Event Protocol version (semver string).
metadata   : Arbitrary cross-cutting annotations (trace IDs, tags, etc.).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return the current UTC-aware datetime."""
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    """Return a fresh UUID4 as a string."""
    return str(uuid4())


# ---------------------------------------------------------------------------
# AgentStartedEvent
# ---------------------------------------------------------------------------


class AgentStartedEvent(BaseModel):
    """Emitted when an agent process transitions from idle to running.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Stable identifier of the agent that started.
    event_type:
        Always ``"agent_started"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    runtime:
        Runtime environment label, e.g. ``"python"``, ``"node"``.
    entrypoint:
        Name of the entry-point function or task that was invoked.
    config_hash:
        Optional hash of the agent's configuration snapshot.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["agent_started"] = "agent_started"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    # Lifecycle-specific fields
    runtime: str = ""
    entrypoint: str = ""
    config_hash: str = ""


# ---------------------------------------------------------------------------
# AgentCompletedEvent
# ---------------------------------------------------------------------------


class AgentCompletedEvent(BaseModel):
    """Emitted when an agent process finishes successfully.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Stable identifier of the agent.
    event_type:
        Always ``"agent_completed"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    duration_ms:
        Wall-clock execution time in milliseconds.
    output_summary:
        Brief human-readable description of the output produced.
    total_cost_usd:
        Accumulated API spend during this agent run (USD).
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["agent_completed"] = "agent_completed"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    # Lifecycle-specific fields
    duration_ms: float = 0.0
    output_summary: str = ""
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# AgentFailedEvent
# ---------------------------------------------------------------------------


class AgentFailedEvent(BaseModel):
    """Emitted when an agent process terminates due to an unhandled error.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Stable identifier of the agent.
    event_type:
        Always ``"agent_failed"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    error_type:
        The Python exception class name or error category.
    error_message:
        Human-readable description of the failure.
    traceback:
        Optional formatted traceback string for debugging.
    duration_ms:
        Wall-clock execution time before failure in milliseconds.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["agent_failed"] = "agent_failed"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    # Failure-specific fields
    error_type: str = ""
    error_message: str = ""
    traceback: str = ""
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# AgentPausedEvent
# ---------------------------------------------------------------------------


class AgentPausedEvent(BaseModel):
    """Emitted when an agent process suspends execution and awaits resumption.

    Pause/resume pairs are used for human-in-the-loop workflows and
    checkpoint-based execution.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Stable identifier of the agent.
    event_type:
        Always ``"agent_paused"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    pause_reason:
        Human-readable description of why execution was suspended.
    checkpoint_id:
        Identifier of the persisted checkpoint (if applicable).
    awaiting_input:
        Whether the agent is blocked waiting for external input.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["agent_paused"] = "agent_paused"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    # Pause-specific fields
    pause_reason: str = ""
    checkpoint_id: str = ""
    awaiting_input: bool = False


# ---------------------------------------------------------------------------
# AgentResumedEvent
# ---------------------------------------------------------------------------


class AgentResumedEvent(BaseModel):
    """Emitted when a paused agent process resumes execution.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Stable identifier of the agent.
    event_type:
        Always ``"agent_resumed"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    resumed_from_checkpoint:
        ID of the checkpoint the agent resumed from.
    pause_duration_ms:
        Wall-clock time the agent spent in the paused state (ms).
    resumed_by:
        Identifier of the entity (user/system) that triggered resumption.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["agent_resumed"] = "agent_resumed"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    # Resume-specific fields
    resumed_from_checkpoint: str = ""
    pause_duration_ms: float = 0.0
    resumed_by: str = ""
