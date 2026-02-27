"""Tool event schemas — invoke, complete, fail, abort.

These events are emitted during the tool-call sub-lifecycle of an agent turn.
Each event captures the tool name, invocation identifier (to correlate invoke
with complete/fail), and relevant payload fields.

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
# ToolInvokedEvent
# ---------------------------------------------------------------------------


class ToolInvokedEvent(BaseModel):
    """Emitted immediately before a tool is called.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Identifier of the agent making the call.
    event_type:
        Always ``"tool_invoked"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    invocation_id:
        Unique ID for this specific tool invocation; used to correlate with
        the corresponding complete/fail/abort event.
    tool_name:
        Canonical name of the tool being called.
    tool_version:
        Version string of the tool, if known.
    input_args:
        Arguments passed to the tool (JSON-safe mapping).
    call_reason:
        Optional description of why the agent chose this tool.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["tool_invoked"] = "tool_invoked"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    invocation_id: str = Field(default_factory=_new_uuid)
    tool_name: str
    tool_version: str = ""
    input_args: dict[str, object] = Field(default_factory=dict)
    call_reason: str = ""


# ---------------------------------------------------------------------------
# ToolCompletedEvent
# ---------------------------------------------------------------------------


class ToolCompletedEvent(BaseModel):
    """Emitted when a tool call returns a successful result.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Identifier of the agent that made the call.
    event_type:
        Always ``"tool_completed"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    invocation_id:
        Matches the ``invocation_id`` from the corresponding
        ``ToolInvokedEvent``.
    tool_name:
        Canonical name of the tool that was called.
    duration_ms:
        Wall-clock execution time in milliseconds.
    output_summary:
        Brief description of the result for tracing purposes.
    token_cost:
        Tokens consumed by this tool call, if measurable.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["tool_completed"] = "tool_completed"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    invocation_id: str = ""
    tool_name: str
    duration_ms: float = 0.0
    output_summary: str = ""
    token_cost: int = 0


# ---------------------------------------------------------------------------
# ToolFailedEvent
# ---------------------------------------------------------------------------


class ToolFailedEvent(BaseModel):
    """Emitted when a tool call raises an error or returns a failure status.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Identifier of the agent that made the call.
    event_type:
        Always ``"tool_failed"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    invocation_id:
        Matches the ``invocation_id`` from the corresponding
        ``ToolInvokedEvent``.
    tool_name:
        Canonical name of the tool that failed.
    error_type:
        Python exception class name or error category.
    error_message:
        Human-readable description of the failure.
    duration_ms:
        Wall-clock execution time before failure in milliseconds.
    retryable:
        Whether the caller should attempt to retry this invocation.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["tool_failed"] = "tool_failed"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    invocation_id: str = ""
    tool_name: str
    error_type: str = ""
    error_message: str = ""
    duration_ms: float = 0.0
    retryable: bool = False


# ---------------------------------------------------------------------------
# ToolAbortedEvent
# ---------------------------------------------------------------------------


class ToolAbortedEvent(BaseModel):
    """Emitted when a tool invocation is cancelled before completion.

    An abort is distinct from a failure: the tool was deliberately stopped
    by a governance policy, timeout, or user intervention rather than
    encountering an unexpected error.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Identifier of the agent that made the call.
    event_type:
        Always ``"tool_aborted"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    invocation_id:
        Matches the ``invocation_id`` from the corresponding
        ``ToolInvokedEvent``.
    tool_name:
        Canonical name of the tool that was aborted.
    abort_reason:
        Description of why the invocation was cancelled.
    aborted_by:
        Identifier of the entity (policy/user/system) that triggered abort.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["tool_aborted"] = "tool_aborted"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    invocation_id: str = ""
    tool_name: str
    abort_reason: str = ""
    aborted_by: str = ""
