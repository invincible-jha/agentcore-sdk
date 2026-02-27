"""Approval event schemas — human approval requested and received.

Human approval events are emitted during human-in-the-loop workflows where an
agent must pause and wait for explicit authorisation before proceeding.

The typical flow is:
1. Agent emits ``HumanApprovalRequestedEvent`` and blocks.
2. A human reviewer sees the request and makes a decision.
3. The decision is fed back to the agent, which emits
   ``HumanApprovalReceivedEvent`` and either continues or halts.

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
# HumanApprovalRequestedEvent
# ---------------------------------------------------------------------------


class HumanApprovalRequestedEvent(BaseModel):
    """Emitted when an agent requests human authorisation to proceed.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the request was raised.
    agent_id:
        Identifier of the agent requesting approval.
    event_type:
        Always ``"human_approval_requested"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    approval_id:
        Unique identifier for this approval cycle; correlates with the
        corresponding ``HumanApprovalReceivedEvent``.
    action_summary:
        Human-readable description of the action awaiting approval.
    risk_level:
        Categorical risk assessment: ``"low"``, ``"medium"``, or ``"high"``.
    context_summary:
        Background context to assist the reviewer in making a decision.
    deadline_iso:
        Optional ISO 8601 UTC deadline by which approval is needed.
    escalation_path:
        Comma-separated list of reviewer roles in priority order.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["human_approval_requested"] = "human_approval_requested"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    approval_id: str = Field(default_factory=_new_uuid)
    action_summary: str = ""
    risk_level: Literal["low", "medium", "high"] = "medium"
    context_summary: str = ""
    deadline_iso: str = ""
    escalation_path: str = ""


# ---------------------------------------------------------------------------
# HumanApprovalReceivedEvent
# ---------------------------------------------------------------------------


class HumanApprovalReceivedEvent(BaseModel):
    """Emitted when an agent receives the human reviewer's decision.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the decision was received.
    agent_id:
        Identifier of the agent that requested approval.
    event_type:
        Always ``"human_approval_received"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    approval_id:
        Matches the ``approval_id`` from ``HumanApprovalRequestedEvent``.
    approved:
        True if the reviewer granted approval; False if denied.
    reviewer_id:
        Identifier of the human reviewer who made the decision.
    reviewer_notes:
        Optional free-text notes from the reviewer.
    wait_duration_ms:
        Wall-clock time from request to decision receipt in milliseconds.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["human_approval_received"] = "human_approval_received"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    approval_id: str = ""
    approved: bool = False
    reviewer_id: str = ""
    reviewer_notes: str = ""
    wait_duration_ms: float = 0.0
