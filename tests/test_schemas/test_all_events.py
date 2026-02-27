"""Tests for agentcore.schemas — universal agent event models.

Covers:
- Construction with defaults and explicit values
- Frozen immutability enforcement
- Pydantic serialisation round-trips (model_dump / model_validate)
- JSON round-trips
- Literal event_type enforcement
- Field-level validation
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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
from agentcore.schemas import (  # package-level re-exports
    AgentStartedEvent as PkgAgentStartedEvent,
    ToolInvokedEvent as PkgToolInvokedEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AGENT_ID = "test-agent-001"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================================================
# AgentStartedEvent
# ===========================================================================


class TestAgentStartedEvent:
    def test_construction_defaults(self) -> None:
        event = AgentStartedEvent(agent_id=_AGENT_ID)
        assert event.agent_id == _AGENT_ID
        assert event.event_type == "agent_started"
        assert event.aep_version == "1.0.0"
        assert len(event.event_id) == 36  # UUID4 format
        assert event.runtime == ""
        assert event.entrypoint == ""
        assert event.config_hash == ""
        assert event.metadata == {}

    def test_construction_explicit(self) -> None:
        event = AgentStartedEvent(
            agent_id=_AGENT_ID,
            runtime="python",
            entrypoint="main",
            config_hash="abc123",
            metadata={"env": "prod"},
        )
        assert event.runtime == "python"
        assert event.entrypoint == "main"
        assert event.config_hash == "abc123"
        assert event.metadata == {"env": "prod"}

    def test_frozen(self) -> None:
        event = AgentStartedEvent(agent_id=_AGENT_ID)
        with pytest.raises((TypeError, ValidationError)):
            event.agent_id = "other"  # type: ignore[misc]

    def test_timestamp_is_utc_aware(self) -> None:
        event = AgentStartedEvent(agent_id=_AGENT_ID)
        assert event.timestamp.tzinfo is not None

    def test_event_ids_are_unique(self) -> None:
        e1 = AgentStartedEvent(agent_id=_AGENT_ID)
        e2 = AgentStartedEvent(agent_id=_AGENT_ID)
        assert e1.event_id != e2.event_id

    def test_serialisation_round_trip(self) -> None:
        event = AgentStartedEvent(
            agent_id=_AGENT_ID, runtime="python", config_hash="sha256:abc"
        )
        dumped = event.model_dump()
        restored = AgentStartedEvent.model_validate(dumped)
        assert restored.event_id == event.event_id
        assert restored.runtime == event.runtime

    def test_json_round_trip(self) -> None:
        event = AgentStartedEvent(agent_id=_AGENT_ID, entrypoint="run")
        json_str = event.model_dump_json()
        data = json.loads(json_str)
        assert data["event_type"] == "agent_started"
        restored = AgentStartedEvent.model_validate_json(json_str)
        assert restored.event_id == event.event_id


# ===========================================================================
# AgentCompletedEvent
# ===========================================================================


class TestAgentCompletedEvent:
    def test_defaults(self) -> None:
        event = AgentCompletedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "agent_completed"
        assert event.duration_ms == 0.0
        assert event.output_summary == ""
        assert event.total_cost_usd == 0.0

    def test_explicit_fields(self) -> None:
        event = AgentCompletedEvent(
            agent_id=_AGENT_ID,
            duration_ms=1234.5,
            output_summary="Generated report",
            total_cost_usd=0.0042,
        )
        assert event.duration_ms == 1234.5
        assert event.output_summary == "Generated report"
        assert event.total_cost_usd == pytest.approx(0.0042)

    def test_serialisation(self) -> None:
        event = AgentCompletedEvent(agent_id=_AGENT_ID, duration_ms=500.0)
        d = event.model_dump()
        assert d["event_type"] == "agent_completed"
        assert d["duration_ms"] == 500.0

    def test_json_round_trip(self) -> None:
        event = AgentCompletedEvent(agent_id=_AGENT_ID, total_cost_usd=0.01)
        restored = AgentCompletedEvent.model_validate_json(event.model_dump_json())
        assert restored.total_cost_usd == event.total_cost_usd


# ===========================================================================
# AgentFailedEvent
# ===========================================================================


class TestAgentFailedEvent:
    def test_defaults(self) -> None:
        event = AgentFailedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "agent_failed"
        assert event.error_type == ""
        assert event.error_message == ""
        assert event.traceback == ""
        assert event.duration_ms == 0.0

    def test_failure_fields(self) -> None:
        event = AgentFailedEvent(
            agent_id=_AGENT_ID,
            error_type="RuntimeError",
            error_message="Out of memory",
            traceback="Traceback (most recent call last)...",
            duration_ms=99.9,
        )
        assert event.error_type == "RuntimeError"
        assert event.error_message == "Out of memory"
        assert "Traceback" in event.traceback

    def test_round_trip(self) -> None:
        event = AgentFailedEvent(agent_id=_AGENT_ID, error_type="ValueError")
        restored = AgentFailedEvent.model_validate(event.model_dump())
        assert restored.error_type == "ValueError"


# ===========================================================================
# AgentPausedEvent
# ===========================================================================


class TestAgentPausedEvent:
    def test_defaults(self) -> None:
        event = AgentPausedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "agent_paused"
        assert event.pause_reason == ""
        assert event.checkpoint_id == ""
        assert event.awaiting_input is False

    def test_explicit(self) -> None:
        event = AgentPausedEvent(
            agent_id=_AGENT_ID,
            pause_reason="Awaiting human approval",
            checkpoint_id="ckpt-001",
            awaiting_input=True,
        )
        assert event.awaiting_input is True
        assert event.checkpoint_id == "ckpt-001"

    def test_json(self) -> None:
        event = AgentPausedEvent(agent_id=_AGENT_ID, awaiting_input=True)
        d = json.loads(event.model_dump_json())
        assert d["awaiting_input"] is True
        assert d["event_type"] == "agent_paused"


# ===========================================================================
# AgentResumedEvent
# ===========================================================================


class TestAgentResumedEvent:
    def test_defaults(self) -> None:
        event = AgentResumedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "agent_resumed"
        assert event.resumed_from_checkpoint == ""
        assert event.pause_duration_ms == 0.0
        assert event.resumed_by == ""

    def test_explicit(self) -> None:
        event = AgentResumedEvent(
            agent_id=_AGENT_ID,
            resumed_from_checkpoint="ckpt-001",
            pause_duration_ms=5000.0,
            resumed_by="user-42",
        )
        assert event.resumed_by == "user-42"
        assert event.pause_duration_ms == 5000.0

    def test_round_trip(self) -> None:
        event = AgentResumedEvent(agent_id=_AGENT_ID, resumed_by="scheduler")
        restored = AgentResumedEvent.model_validate(event.model_dump())
        assert restored.resumed_by == "scheduler"


# ===========================================================================
# ToolInvokedEvent
# ===========================================================================


class TestToolInvokedEvent:
    def test_defaults(self) -> None:
        event = ToolInvokedEvent(agent_id=_AGENT_ID, tool_name="web_search")
        assert event.event_type == "tool_invoked"
        assert event.tool_name == "web_search"
        assert event.tool_version == ""
        assert event.input_args == {}
        assert event.call_reason == ""
        # invocation_id is auto-generated
        assert len(event.invocation_id) == 36

    def test_explicit_args(self) -> None:
        event = ToolInvokedEvent(
            agent_id=_AGENT_ID,
            tool_name="code_executor",
            tool_version="2.1.0",
            input_args={"code": "print('hello')"},
            call_reason="Run code snippet",
        )
        assert event.input_args["code"] == "print('hello')"
        assert event.tool_version == "2.1.0"

    def test_invocation_ids_unique(self) -> None:
        e1 = ToolInvokedEvent(agent_id=_AGENT_ID, tool_name="t")
        e2 = ToolInvokedEvent(agent_id=_AGENT_ID, tool_name="t")
        assert e1.invocation_id != e2.invocation_id

    def test_json_round_trip(self) -> None:
        event = ToolInvokedEvent(
            agent_id=_AGENT_ID, tool_name="search", input_args={"q": "ai"}
        )
        restored = ToolInvokedEvent.model_validate_json(event.model_dump_json())
        assert restored.input_args == {"q": "ai"}


# ===========================================================================
# ToolCompletedEvent
# ===========================================================================


class TestToolCompletedEvent:
    def test_defaults(self) -> None:
        event = ToolCompletedEvent(agent_id=_AGENT_ID, tool_name="search")
        assert event.event_type == "tool_completed"
        assert event.duration_ms == 0.0
        assert event.output_summary == ""
        assert event.token_cost == 0

    def test_correlation(self) -> None:
        invoked = ToolInvokedEvent(agent_id=_AGENT_ID, tool_name="search")
        completed = ToolCompletedEvent(
            agent_id=_AGENT_ID,
            tool_name="search",
            invocation_id=invoked.invocation_id,
            duration_ms=250.0,
            output_summary="3 results",
        )
        assert completed.invocation_id == invoked.invocation_id

    def test_serialisation(self) -> None:
        event = ToolCompletedEvent(agent_id=_AGENT_ID, tool_name="t", token_cost=50)
        d = event.model_dump()
        assert d["token_cost"] == 50
        assert d["event_type"] == "tool_completed"


# ===========================================================================
# ToolFailedEvent
# ===========================================================================


class TestToolFailedEvent:
    def test_defaults(self) -> None:
        event = ToolFailedEvent(agent_id=_AGENT_ID, tool_name="search")
        assert event.event_type == "tool_failed"
        assert event.retryable is False
        assert event.error_type == ""

    def test_failure_detail(self) -> None:
        event = ToolFailedEvent(
            agent_id=_AGENT_ID,
            tool_name="search",
            error_type="TimeoutError",
            error_message="Request timed out",
            retryable=True,
            duration_ms=5000.0,
        )
        assert event.retryable is True
        assert event.error_type == "TimeoutError"

    def test_json_round_trip(self) -> None:
        event = ToolFailedEvent(agent_id=_AGENT_ID, tool_name="t", retryable=True)
        restored = ToolFailedEvent.model_validate_json(event.model_dump_json())
        assert restored.retryable is True


# ===========================================================================
# ToolAbortedEvent
# ===========================================================================


class TestToolAbortedEvent:
    def test_defaults(self) -> None:
        event = ToolAbortedEvent(agent_id=_AGENT_ID, tool_name="exec")
        assert event.event_type == "tool_aborted"
        assert event.abort_reason == ""
        assert event.aborted_by == ""

    def test_explicit(self) -> None:
        event = ToolAbortedEvent(
            agent_id=_AGENT_ID,
            tool_name="exec",
            abort_reason="Policy violation",
            aborted_by="governance-layer",
        )
        assert event.aborted_by == "governance-layer"

    def test_round_trip(self) -> None:
        event = ToolAbortedEvent(
            agent_id=_AGENT_ID, tool_name="t", abort_reason="timeout"
        )
        restored = ToolAbortedEvent.model_validate(event.model_dump())
        assert restored.abort_reason == "timeout"


# ===========================================================================
# LLMCalledEvent
# ===========================================================================


class TestLLMCalledEvent:
    def test_defaults(self) -> None:
        event = LLMCalledEvent(agent_id=_AGENT_ID)
        assert event.event_type == "llm_called"
        assert event.model_name == ""
        assert event.temperature == 1.0
        assert event.streaming is False
        assert len(event.call_id) == 36

    def test_explicit(self) -> None:
        event = LLMCalledEvent(
            agent_id=_AGENT_ID,
            model_name="gpt-4o",
            provider="openai",
            prompt_tokens=512,
            temperature=0.2,
            max_tokens=1024,
            streaming=True,
        )
        assert event.model_name == "gpt-4o"
        assert event.streaming is True
        assert event.temperature == pytest.approx(0.2)

    def test_json_round_trip(self) -> None:
        event = LLMCalledEvent(agent_id=_AGENT_ID, model_name="claude-3", streaming=True)
        restored = LLMCalledEvent.model_validate_json(event.model_dump_json())
        assert restored.model_name == "claude-3"
        assert restored.streaming is True


# ===========================================================================
# LLMRespondedEvent
# ===========================================================================


class TestLLMRespondedEvent:
    def test_defaults(self) -> None:
        event = LLMRespondedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "llm_responded"
        assert event.finish_reason == "stop"
        assert event.total_tokens == 0
        assert event.cost_usd == 0.0

    def test_token_accounting(self) -> None:
        event = LLMRespondedEvent(
            agent_id=_AGENT_ID,
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            cost_usd=0.006,
        )
        assert event.total_tokens == 300
        assert event.cost_usd == pytest.approx(0.006)

    def test_correlation_with_called(self) -> None:
        called = LLMCalledEvent(agent_id=_AGENT_ID, model_name="gpt-4o")
        responded = LLMRespondedEvent(
            agent_id=_AGENT_ID,
            call_id=called.call_id,
            model_name="gpt-4o",
            duration_ms=1500.0,
        )
        assert responded.call_id == called.call_id

    def test_round_trip(self) -> None:
        event = LLMRespondedEvent(agent_id=_AGENT_ID, finish_reason="length")
        restored = LLMRespondedEvent.model_validate(event.model_dump())
        assert restored.finish_reason == "length"


# ===========================================================================
# LLMStreamChunkEvent
# ===========================================================================


class TestLLMStreamChunkEvent:
    def test_defaults(self) -> None:
        event = LLMStreamChunkEvent(agent_id=_AGENT_ID)
        assert event.event_type == "llm_stream_chunk"
        assert event.chunk_index == 0
        assert event.delta == ""
        assert event.is_final is False

    def test_chunk_sequence(self) -> None:
        called = LLMCalledEvent(agent_id=_AGENT_ID, streaming=True)
        chunks = [
            LLMStreamChunkEvent(
                agent_id=_AGENT_ID,
                call_id=called.call_id,
                chunk_index=i,
                delta=f"token{i}",
                is_final=(i == 2),
            )
            for i in range(3)
        ]
        assert chunks[0].is_final is False
        assert chunks[2].is_final is True
        assert all(c.call_id == called.call_id for c in chunks)

    def test_json_round_trip(self) -> None:
        event = LLMStreamChunkEvent(
            agent_id=_AGENT_ID, chunk_index=5, delta="hello", is_final=True
        )
        restored = LLMStreamChunkEvent.model_validate_json(event.model_dump_json())
        assert restored.delta == "hello"
        assert restored.is_final is True


# ===========================================================================
# MemoryReadEvent
# ===========================================================================


class TestMemoryReadEvent:
    def test_defaults(self) -> None:
        event = MemoryReadEvent(agent_id=_AGENT_ID)
        assert event.event_type == "memory_read"
        assert event.memory_scope == "session"
        assert event.items_returned == 0
        assert event.cache_hit is False

    def test_explicit(self) -> None:
        event = MemoryReadEvent(
            agent_id=_AGENT_ID,
            memory_key="user_prefs",
            memory_scope="user",
            items_returned=5,
            query_summary="user preferences for formatting",
            cache_hit=True,
        )
        assert event.cache_hit is True
        assert event.items_returned == 5
        assert event.memory_scope == "user"

    def test_round_trip(self) -> None:
        event = MemoryReadEvent(agent_id=_AGENT_ID, memory_key="k1", cache_hit=True)
        restored = MemoryReadEvent.model_validate(event.model_dump())
        assert restored.cache_hit is True


# ===========================================================================
# MemoryWriteEvent
# ===========================================================================


class TestMemoryWriteEvent:
    def test_defaults(self) -> None:
        event = MemoryWriteEvent(agent_id=_AGENT_ID)
        assert event.event_type == "memory_write"
        assert event.operation == "upsert"
        assert event.items_written == 0
        assert event.size_bytes == 0

    def test_operations(self) -> None:
        for op in ("insert", "update", "upsert"):
            event = MemoryWriteEvent(agent_id=_AGENT_ID, operation=op)  # type: ignore[arg-type]
            assert event.operation == op

    def test_invalid_operation(self) -> None:
        with pytest.raises(ValidationError):
            MemoryWriteEvent(agent_id=_AGENT_ID, operation="delete")  # type: ignore[arg-type]

    def test_explicit(self) -> None:
        event = MemoryWriteEvent(
            agent_id=_AGENT_ID,
            memory_key="task_state",
            operation="update",
            items_written=1,
            size_bytes=512,
        )
        assert event.size_bytes == 512
        assert event.items_written == 1

    def test_json_round_trip(self) -> None:
        event = MemoryWriteEvent(agent_id=_AGENT_ID, memory_key="k", operation="insert")
        restored = MemoryWriteEvent.model_validate_json(event.model_dump_json())
        assert restored.operation == "insert"


# ===========================================================================
# MemoryDeletedEvent
# ===========================================================================


class TestMemoryDeletedEvent:
    def test_defaults(self) -> None:
        event = MemoryDeletedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "memory_deleted"
        assert event.items_deleted == 0
        assert event.deletion_reason == ""

    def test_explicit(self) -> None:
        event = MemoryDeletedEvent(
            agent_id=_AGENT_ID,
            memory_key="old_session",
            items_deleted=10,
            deletion_reason="TTL expired",
        )
        assert event.items_deleted == 10
        assert event.deletion_reason == "TTL expired"

    def test_round_trip(self) -> None:
        event = MemoryDeletedEvent(agent_id=_AGENT_ID, items_deleted=3)
        restored = MemoryDeletedEvent.model_validate(event.model_dump())
        assert restored.items_deleted == 3


# ===========================================================================
# DelegationSentEvent
# ===========================================================================


class TestDelegationSentEvent:
    def test_defaults(self) -> None:
        event = DelegationSentEvent(agent_id=_AGENT_ID)
        assert event.event_type == "delegation_sent"
        assert event.target_agent_id == ""
        assert event.priority == 5
        assert len(event.delegation_id) == 36

    def test_explicit(self) -> None:
        event = DelegationSentEvent(
            agent_id=_AGENT_ID,
            target_agent_id="worker-001",
            task_summary="Analyse the report",
            priority=2,
            deadline_iso="2026-12-31T23:59:59Z",
        )
        assert event.target_agent_id == "worker-001"
        assert event.priority == 2

    def test_json_round_trip(self) -> None:
        event = DelegationSentEvent(agent_id=_AGENT_ID, target_agent_id="w1")
        restored = DelegationSentEvent.model_validate_json(event.model_dump_json())
        assert restored.delegation_id == event.delegation_id


# ===========================================================================
# DelegationReceivedEvent
# ===========================================================================


class TestDelegationReceivedEvent:
    def test_defaults(self) -> None:
        event = DelegationReceivedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "delegation_received"
        assert event.accepted is True
        assert event.rejection_reason == ""

    def test_rejection(self) -> None:
        event = DelegationReceivedEvent(
            agent_id=_AGENT_ID,
            accepted=False,
            rejection_reason="Capacity limit reached",
        )
        assert event.accepted is False
        assert "Capacity" in event.rejection_reason

    def test_correlation(self) -> None:
        sent = DelegationSentEvent(agent_id="orchestrator")
        received = DelegationReceivedEvent(
            agent_id="worker-001",
            delegation_id=sent.delegation_id,
            source_agent_id="orchestrator",
        )
        assert received.delegation_id == sent.delegation_id

    def test_round_trip(self) -> None:
        event = DelegationReceivedEvent(agent_id=_AGENT_ID, accepted=False)
        restored = DelegationReceivedEvent.model_validate(event.model_dump())
        assert restored.accepted is False


# ===========================================================================
# DelegationCompletedEvent
# ===========================================================================


class TestDelegationCompletedEvent:
    def test_defaults(self) -> None:
        event = DelegationCompletedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "delegation_completed"
        assert event.success is True
        assert event.result_summary == ""
        assert event.duration_ms == 0.0

    def test_failure(self) -> None:
        event = DelegationCompletedEvent(
            agent_id=_AGENT_ID,
            success=False,
            error_message="Worker OOM",
            duration_ms=3200.0,
        )
        assert event.success is False
        assert event.error_message == "Worker OOM"

    def test_full_lifecycle(self) -> None:
        sent = DelegationSentEvent(agent_id="orch", target_agent_id="worker")
        received = DelegationReceivedEvent(
            agent_id="worker",
            delegation_id=sent.delegation_id,
            source_agent_id="orch",
        )
        completed = DelegationCompletedEvent(
            agent_id="worker",
            delegation_id=sent.delegation_id,
            source_agent_id="orch",
            success=True,
            result_summary="Done",
            duration_ms=1000.0,
        )
        assert completed.delegation_id == sent.delegation_id == received.delegation_id

    def test_json_round_trip(self) -> None:
        event = DelegationCompletedEvent(agent_id=_AGENT_ID, duration_ms=500.0)
        restored = DelegationCompletedEvent.model_validate_json(event.model_dump_json())
        assert restored.duration_ms == 500.0


# ===========================================================================
# HumanApprovalRequestedEvent
# ===========================================================================


class TestHumanApprovalRequestedEvent:
    def test_defaults(self) -> None:
        event = HumanApprovalRequestedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "human_approval_requested"
        assert event.risk_level == "medium"
        assert event.action_summary == ""
        assert len(event.approval_id) == 36

    def test_explicit(self) -> None:
        event = HumanApprovalRequestedEvent(
            agent_id=_AGENT_ID,
            action_summary="Delete customer records",
            risk_level="high",
            context_summary="Requested by automated cleanup policy",
            deadline_iso="2026-12-01T00:00:00Z",
            escalation_path="manager,ciso",
        )
        assert event.risk_level == "high"
        assert event.escalation_path == "manager,ciso"

    def test_invalid_risk_level(self) -> None:
        with pytest.raises(ValidationError):
            HumanApprovalRequestedEvent(
                agent_id=_AGENT_ID, risk_level="critical"  # type: ignore[arg-type]
            )

    def test_json_round_trip(self) -> None:
        event = HumanApprovalRequestedEvent(
            agent_id=_AGENT_ID, risk_level="low", action_summary="Read file"
        )
        restored = HumanApprovalRequestedEvent.model_validate_json(
            event.model_dump_json()
        )
        assert restored.risk_level == "low"
        assert restored.approval_id == event.approval_id


# ===========================================================================
# HumanApprovalReceivedEvent
# ===========================================================================


class TestHumanApprovalReceivedEvent:
    def test_defaults(self) -> None:
        event = HumanApprovalReceivedEvent(agent_id=_AGENT_ID)
        assert event.event_type == "human_approval_received"
        assert event.approved is False
        assert event.reviewer_id == ""
        assert event.wait_duration_ms == 0.0

    def test_approval(self) -> None:
        event = HumanApprovalReceivedEvent(
            agent_id=_AGENT_ID,
            approved=True,
            reviewer_id="analyst-007",
            reviewer_notes="Looks safe to proceed",
            wait_duration_ms=120000.0,
        )
        assert event.approved is True
        assert event.reviewer_id == "analyst-007"
        assert event.wait_duration_ms == 120000.0

    def test_full_lifecycle(self) -> None:
        requested = HumanApprovalRequestedEvent(
            agent_id=_AGENT_ID, action_summary="Deploy to prod"
        )
        received = HumanApprovalReceivedEvent(
            agent_id=_AGENT_ID,
            approval_id=requested.approval_id,
            approved=True,
            reviewer_id="lead-engineer",
        )
        assert received.approval_id == requested.approval_id

    def test_round_trip(self) -> None:
        event = HumanApprovalReceivedEvent(
            agent_id=_AGENT_ID, approved=True, reviewer_id="bob"
        )
        restored = HumanApprovalReceivedEvent.model_validate(event.model_dump())
        assert restored.reviewer_id == "bob"


# ===========================================================================
# Package-level re-export tests
# ===========================================================================


class TestPackageReExports:
    def test_agent_started_re_exported(self) -> None:
        event = PkgAgentStartedEvent(agent_id="pkg-agent")
        assert event.event_type == "agent_started"

    def test_tool_invoked_re_exported(self) -> None:
        event = PkgToolInvokedEvent(agent_id="pkg-agent", tool_name="search")
        assert event.tool_name == "search"


# ===========================================================================
# Cross-cutting: all events have stable schema fields
# ===========================================================================


ALL_EVENT_CLASSES = [
    (AgentStartedEvent, {"agent_id": _AGENT_ID}),
    (AgentCompletedEvent, {"agent_id": _AGENT_ID}),
    (AgentFailedEvent, {"agent_id": _AGENT_ID}),
    (AgentPausedEvent, {"agent_id": _AGENT_ID}),
    (AgentResumedEvent, {"agent_id": _AGENT_ID}),
    (ToolInvokedEvent, {"agent_id": _AGENT_ID, "tool_name": "t"}),
    (ToolCompletedEvent, {"agent_id": _AGENT_ID, "tool_name": "t"}),
    (ToolFailedEvent, {"agent_id": _AGENT_ID, "tool_name": "t"}),
    (ToolAbortedEvent, {"agent_id": _AGENT_ID, "tool_name": "t"}),
    (LLMCalledEvent, {"agent_id": _AGENT_ID}),
    (LLMRespondedEvent, {"agent_id": _AGENT_ID}),
    (LLMStreamChunkEvent, {"agent_id": _AGENT_ID}),
    (MemoryReadEvent, {"agent_id": _AGENT_ID}),
    (MemoryWriteEvent, {"agent_id": _AGENT_ID}),
    (MemoryDeletedEvent, {"agent_id": _AGENT_ID}),
    (DelegationSentEvent, {"agent_id": _AGENT_ID}),
    (DelegationReceivedEvent, {"agent_id": _AGENT_ID}),
    (DelegationCompletedEvent, {"agent_id": _AGENT_ID}),
    (HumanApprovalRequestedEvent, {"agent_id": _AGENT_ID}),
    (HumanApprovalReceivedEvent, {"agent_id": _AGENT_ID}),
]


@pytest.mark.parametrize("event_cls,kwargs", ALL_EVENT_CLASSES)
def test_all_events_have_required_fields(event_cls: type, kwargs: dict) -> None:
    """Every event must have event_id, timestamp, agent_id, event_type."""
    event = event_cls(**kwargs)
    assert hasattr(event, "event_id")
    assert hasattr(event, "timestamp")
    assert hasattr(event, "agent_id")
    assert hasattr(event, "event_type")
    assert event.agent_id == _AGENT_ID
    assert isinstance(event.timestamp, datetime)


@pytest.mark.parametrize("event_cls,kwargs", ALL_EVENT_CLASSES)
def test_all_events_json_round_trip(event_cls: type, kwargs: dict) -> None:
    """Every event must survive a JSON serialisation round-trip."""
    event = event_cls(**kwargs)
    json_str = event.model_dump_json()
    restored = event_cls.model_validate_json(json_str)
    assert restored.event_id == event.event_id
    assert restored.agent_id == event.agent_id


@pytest.mark.parametrize("event_cls,kwargs", ALL_EVENT_CLASSES)
def test_all_events_are_frozen(event_cls: type, kwargs: dict) -> None:
    """Every event model must be immutable (frozen=True)."""
    event = event_cls(**kwargs)
    with pytest.raises((TypeError, ValidationError)):
        event.agent_id = "mutated"  # type: ignore[misc]
