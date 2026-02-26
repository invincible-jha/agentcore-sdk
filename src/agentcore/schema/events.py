"""Event schema definitions for agentcore-sdk.

This module is part of the *public* schema surface.  All event types used
across AumOS platforms are defined here so that producers and consumers share
a single canonical contract.

Shipped in this module
----------------------
- EventType       — canonical taxonomy of agent lifecycle events
- AgentEvent      — base event dataclass with serde helpers
- ToolCallEvent   — specialised event for tool invocations
- DecisionEvent   — specialised event for agent decisions

Withheld / internal
-------------------
Persistence adapters, stream-encoding codecs, and schema-evolution helpers
are not part of this open-source SDK and are available via plugins.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar


class EventType(str, Enum):
    """Canonical taxonomy of agent lifecycle events.

    Using ``str`` as the mixin base means values are valid JSON strings
    without extra serialisation steps.
    """

    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    DECISION_MADE = "decision_made"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    ERROR_OCCURRED = "error_occurred"
    COST_INCURRED = "cost_incurred"
    CUSTOM = "custom"


def _parse_base_fields(
    payload: dict[str, object],
) -> dict[str, object]:
    """Extract and coerce the base AgentEvent fields from a raw dict.

    Returns a kwargs dict suitable for passing to any AgentEvent (or
    subclass) constructor.
    """
    raw_ts = payload.get("timestamp")
    if isinstance(raw_ts, str):
        parsed_ts: datetime = datetime.fromisoformat(raw_ts)
    elif isinstance(raw_ts, datetime):
        parsed_ts = raw_ts
    else:
        parsed_ts = datetime.now(tz=timezone.utc)

    event_type_raw = payload["event_type"]
    event_type = EventType(str(event_type_raw))

    agent_id = str(payload["agent_id"])

    data_raw = payload.get("data", {})
    data: dict[str, object] = dict(data_raw) if isinstance(data_raw, dict) else {}

    meta_raw = payload.get("metadata", {})
    metadata: dict[str, object] = dict(meta_raw) if isinstance(meta_raw, dict) else {}

    event_id_raw = payload.get("event_id")
    event_id = str(event_id_raw) if event_id_raw is not None else str(uuid.uuid4())

    parent_raw = payload.get("parent_event_id")
    parent_event_id: str | None = str(parent_raw) if parent_raw is not None else None

    return {
        "event_type": event_type,
        "agent_id": agent_id,
        "data": data,
        "metadata": metadata,
        "parent_event_id": parent_event_id,
        "timestamp": parsed_ts,
        "event_id": event_id,
    }


@dataclass
class AgentEvent:
    """Base event carrying all fields common to every agent lifecycle signal.

    Parameters
    ----------
    event_type:
        One of the canonical ``EventType`` values.
    agent_id:
        Stable identifier for the agent that emitted this event.
    data:
        Arbitrary payload specific to this event.  Keep values JSON-safe.
    metadata:
        Cross-cutting concerns: trace IDs, tags, environment labels, etc.
    parent_event_id:
        Optional causal link to a parent event (supports event chains).
    timestamp:
        UTC creation time; auto-set to *now* when not provided.
    event_id:
        Globally unique identifier; auto-generated UUID4 when not provided.

    Examples
    --------
    >>> evt = AgentEvent(EventType.AGENT_STARTED, "agent-42")
    >>> isinstance(evt.event_id, str)
    True
    """

    # Required fields first (no default)
    event_type: EventType
    agent_id: str

    # Optional fields with sensible defaults
    data: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
    parent_event_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Subclasses declare their extra serialisable fields here so that
    # to_dict() round-trips cleanly without code changes in base.
    _extra_dict_fields: ClassVar[tuple[str, ...]] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialise the event to a plain dict suitable for JSON encoding.

        Returns
        -------
        dict[str, object]
            All public fields.  ``timestamp`` is ISO-8601, ``event_type`` is
            its string value.
        """
        base: dict[str, object] = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata,
            "parent_event_id": self.parent_event_id,
        }
        for extra_field in self._extra_dict_fields:
            base[extra_field] = getattr(self, extra_field)
        return base

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AgentEvent":
        """Reconstruct an ``AgentEvent`` from a serialised dict.

        Parameters
        ----------
        payload:
            A dict produced by :meth:`to_dict` (or compatible shape).

        Returns
        -------
        AgentEvent
            Fully populated event.

        Raises
        ------
        KeyError
            If required fields are missing from ``payload``.
        ValueError
            If ``event_type`` is not a recognised ``EventType`` value.
        """
        return cls(**_parse_base_fields(payload))  # type: ignore[return-value]


@dataclass
class ToolCallEvent(AgentEvent):
    """Specialised event for tool invocations.

    Adds ``tool_name``, ``tool_input``, and ``tool_output`` fields on top of
    the base ``AgentEvent`` contract.

    Parameters
    ----------
    tool_name:
        The canonical name of the tool that was called.
    tool_input:
        The arguments passed to the tool.
    tool_output:
        The result returned by the tool; ``None`` for TOOL_CALLED events where
        the result is not yet available.

    Examples
    --------
    >>> evt = ToolCallEvent(
    ...     event_type=EventType.TOOL_CALLED,
    ...     agent_id="agent-1",
    ...     tool_name="web_search",
    ...     tool_input={"query": "agentcore"},
    ... )
    """

    tool_name: str = ""
    tool_input: dict[str, object] = field(default_factory=dict)
    tool_output: object = None

    _extra_dict_fields: ClassVar[tuple[str, ...]] = (
        "tool_name",
        "tool_input",
        "tool_output",
    )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ToolCallEvent":  # type: ignore[override]
        """Reconstruct a ``ToolCallEvent`` from a serialised dict."""
        base_kwargs = _parse_base_fields(payload)
        tool_name_raw = payload.get("tool_name", "")
        tool_input_raw = payload.get("tool_input", {})
        return cls(
            **base_kwargs,
            tool_name=str(tool_name_raw),
            tool_input=dict(tool_input_raw) if isinstance(tool_input_raw, dict) else {},
            tool_output=payload.get("tool_output"),
        )  # type: ignore[return-value]


@dataclass
class DecisionEvent(AgentEvent):
    """Specialised event for agent decision points.

    Adds ``decision``, ``reasoning``, and ``confidence`` fields so that
    decision traces can be reconstructed and audited.

    Parameters
    ----------
    decision:
        Short label describing the decision that was made.
    reasoning:
        Free-text explanation of *why* this decision was taken.
    confidence:
        Score in ``[0.0, 1.0]``; ``None`` if the framework does not expose it.

    Examples
    --------
    >>> evt = DecisionEvent(
    ...     event_type=EventType.DECISION_MADE,
    ...     agent_id="agent-1",
    ...     decision="use_tool",
    ...     reasoning="Query requires live data",
    ...     confidence=0.92,
    ... )
    """

    decision: str = ""
    reasoning: str = ""
    confidence: float | None = None

    _extra_dict_fields: ClassVar[tuple[str, ...]] = (
        "decision",
        "reasoning",
        "confidence",
    )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "DecisionEvent":  # type: ignore[override]
        """Reconstruct a ``DecisionEvent`` from a serialised dict."""
        base_kwargs = _parse_base_fields(payload)
        raw_conf = payload.get("confidence")
        return cls(
            **base_kwargs,
            decision=str(payload.get("decision", "")),
            reasoning=str(payload.get("reasoning", "")),
            confidence=float(raw_conf) if raw_conf is not None else None,
        )  # type: ignore[return-value]
