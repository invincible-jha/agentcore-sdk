"""Typed Pydantic event schemas — universal agent event taxonomy.

This package provides strongly-typed Pydantic BaseModel definitions for every
agent lifecycle event category defined by the AumOS platform.  All models use
``model_config`` with ``frozen=True`` to guarantee immutability after
construction.

Modules
-------
lifecycle         — agent start / complete / fail / pause / resume events
tool_events       — tool invoke / complete / fail / abort events
llm_events        — LLM call / response / stream-chunk events
memory_events     — memory read / write / delete events
delegation_events — delegation send / receive / complete events
approval_events   — human approval request / receipt events
"""
from __future__ import annotations

from agentcore.schemas.lifecycle import (
    AgentCompletedEvent,
    AgentFailedEvent,
    AgentPausedEvent,
    AgentResumedEvent,
    AgentStartedEvent,
)
from agentcore.schemas.tool_events import (
    ToolAbortedEvent,
    ToolCompletedEvent,
    ToolFailedEvent,
    ToolInvokedEvent,
)
from agentcore.schemas.llm_events import (
    LLMCalledEvent,
    LLMRespondedEvent,
    LLMStreamChunkEvent,
)
from agentcore.schemas.memory_events import (
    MemoryDeletedEvent,
    MemoryReadEvent,
    MemoryWriteEvent,
)
from agentcore.schemas.delegation_events import (
    DelegationCompletedEvent,
    DelegationReceivedEvent,
    DelegationSentEvent,
)
from agentcore.schemas.approval_events import (
    HumanApprovalReceivedEvent,
    HumanApprovalRequestedEvent,
)

__all__ = [
    # Lifecycle
    "AgentStartedEvent",
    "AgentCompletedEvent",
    "AgentFailedEvent",
    "AgentPausedEvent",
    "AgentResumedEvent",
    # Tool
    "ToolInvokedEvent",
    "ToolCompletedEvent",
    "ToolFailedEvent",
    "ToolAbortedEvent",
    # LLM
    "LLMCalledEvent",
    "LLMRespondedEvent",
    "LLMStreamChunkEvent",
    # Memory
    "MemoryReadEvent",
    "MemoryWriteEvent",
    "MemoryDeletedEvent",
    # Delegation
    "DelegationSentEvent",
    "DelegationReceivedEvent",
    "DelegationCompletedEvent",
    # Approval
    "HumanApprovalRequestedEvent",
    "HumanApprovalReceivedEvent",
]
