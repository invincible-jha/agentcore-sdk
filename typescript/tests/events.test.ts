/**
 * Type-level tests for @aumos/agentcore-types event interfaces.
 *
 * These tests use TypeScript's type system to verify that the interfaces
 * are structurally sound and type guards work correctly.
 */

import {
  type AgentStartedEvent,
  type AgentCompletedEvent,
  type AgentFailedEvent,
  type AgentPausedEvent,
  type AgentResumedEvent,
  type LLMCalledEvent,
  type LLMRespondedEvent,
  type LLMStreamChunkEvent,
  type ToolInvokedEvent,
  type ToolCompletedEvent,
  type ToolFailedEvent,
  type MemoryReadEvent,
  type MemoryWrittenEvent,
  type DelegationRequestedEvent,
  type DelegationCompletedEvent,
  type ApprovalRequestedEvent,
  type ApprovalResolvedEvent,
  type AnyAgentEvent,
  type AgentIdentity,
  type TrustScore,
  isAgentStartedEvent,
  isLLMCalledEvent,
  isLLMRespondedEvent,
  isToolInvokedEvent,
  isMemoryReadEvent,
  isDelegationRequestedEvent,
  isApprovalRequestedEvent,
} from "../src/index.js";

// ---------------------------------------------------------------------------
// Helper: create a base event stub for type assertion tests
// ---------------------------------------------------------------------------

function makeBase(eventType: string) {
  return {
    event_id: "evt-001",
    timestamp: "2024-01-01T00:00:00Z",
    agent_id: "agent-001",
    aep_version: "1.0.0",
    metadata: {},
    event_type: eventType,
  };
}

// ---------------------------------------------------------------------------
// Lifecycle event type assertions
// ---------------------------------------------------------------------------

describe("AgentStartedEvent", () => {
  it("should satisfy the AgentStartedEvent interface", () => {
    const event: AgentStartedEvent = {
      ...makeBase("agent_started"),
      event_type: "agent_started",
      runtime: "python",
      entrypoint: "main",
      config_hash: "abc123",
    };
    expect(event.event_type).toBe("agent_started");
    expect(event.runtime).toBe("python");
  });

  it("should be identified by isAgentStartedEvent guard", () => {
    const event = {
      ...makeBase("agent_started"),
      event_type: "agent_started" as const,
      runtime: "python",
      entrypoint: "main",
      config_hash: "",
    };
    expect(isAgentStartedEvent(event)).toBe(true);
  });

  it("should reject wrong event_type in guard", () => {
    const event = {
      ...makeBase("agent_completed"),
      event_type: "agent_completed" as const,
      duration_ms: 0,
      output_summary: "",
      total_cost_usd: 0,
    };
    expect(isAgentStartedEvent(event)).toBe(false);
  });
});

describe("AgentCompletedEvent", () => {
  it("should satisfy the AgentCompletedEvent interface", () => {
    const event: AgentCompletedEvent = {
      ...makeBase("agent_completed"),
      event_type: "agent_completed",
      duration_ms: 1500.5,
      output_summary: "Task completed",
      total_cost_usd: 0.025,
    };
    expect(event.duration_ms).toBe(1500.5);
    expect(event.total_cost_usd).toBe(0.025);
  });
});

describe("AgentFailedEvent", () => {
  it("should satisfy the AgentFailedEvent interface", () => {
    const event: AgentFailedEvent = {
      ...makeBase("agent_failed"),
      event_type: "agent_failed",
      error_type: "RuntimeError",
      error_message: "Out of memory",
      traceback: "...",
      duration_ms: 500,
    };
    expect(event.error_type).toBe("RuntimeError");
  });
});

// ---------------------------------------------------------------------------
// LLM event type assertions
// ---------------------------------------------------------------------------

describe("LLMCalledEvent", () => {
  it("should satisfy the LLMCalledEvent interface", () => {
    const event: LLMCalledEvent = {
      ...makeBase("llm_called"),
      event_type: "llm_called",
      call_id: "call-001",
      model_name: "gpt-4o",
      provider: "openai",
      prompt_tokens: 500,
      temperature: 0.7,
      max_tokens: 1024,
      streaming: false,
    };
    expect(event.model_name).toBe("gpt-4o");
    expect(event.streaming).toBe(false);
  });

  it("should be identified by isLLMCalledEvent guard", () => {
    const event = {
      ...makeBase("llm_called"),
      event_type: "llm_called" as const,
      call_id: "c1",
      model_name: "claude-opus",
      provider: "anthropic",
      prompt_tokens: 100,
      temperature: 1.0,
      max_tokens: 0,
      streaming: false,
    };
    expect(isLLMCalledEvent(event)).toBe(true);
  });
});

describe("LLMRespondedEvent", () => {
  it("should satisfy the LLMRespondedEvent interface", () => {
    const event: LLMRespondedEvent = {
      ...makeBase("llm_responded"),
      event_type: "llm_responded",
      call_id: "call-001",
      model_name: "gpt-4o",
      provider: "openai",
      prompt_tokens: 500,
      completion_tokens: 250,
      total_tokens: 750,
      duration_ms: 1200,
      finish_reason: "stop",
      cost_usd: 0.015,
    };
    expect(event.total_tokens).toBe(750);
    expect(event.cost_usd).toBe(0.015);
  });

  it("should be identified by isLLMRespondedEvent guard", () => {
    const event = {
      ...makeBase("llm_responded"),
      event_type: "llm_responded" as const,
      call_id: "",
      model_name: "",
      provider: "",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      duration_ms: 0,
      finish_reason: "stop",
      cost_usd: 0,
    };
    expect(isLLMRespondedEvent(event)).toBe(true);
  });
});

describe("LLMStreamChunkEvent", () => {
  it("should satisfy the LLMStreamChunkEvent interface", () => {
    const event: LLMStreamChunkEvent = {
      ...makeBase("llm_stream_chunk"),
      event_type: "llm_stream_chunk",
      call_id: "call-stream-001",
      chunk_index: 5,
      delta: "Hello, ",
      is_final: false,
      model_name: "gpt-4",
    };
    expect(event.chunk_index).toBe(5);
    expect(event.is_final).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Tool event type assertions
// ---------------------------------------------------------------------------

describe("ToolInvokedEvent", () => {
  it("should satisfy the ToolInvokedEvent interface", () => {
    const event: ToolInvokedEvent = {
      ...makeBase("tool_invoked"),
      event_type: "tool_invoked",
      tool_name: "web_search",
      tool_call_id: "tc-001",
      input_schema: { type: "object" },
      input_values: { query: "aumos" },
      framework: "langchain",
    };
    expect(event.tool_name).toBe("web_search");
  });

  it("should be identified by isToolInvokedEvent guard", () => {
    const event = {
      ...makeBase("tool_invoked"),
      event_type: "tool_invoked" as const,
      tool_name: "calculator",
      tool_call_id: "",
      input_schema: {},
      input_values: {},
      framework: "",
    };
    expect(isToolInvokedEvent(event)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Memory event type assertions
// ---------------------------------------------------------------------------

describe("MemoryReadEvent", () => {
  it("should satisfy the MemoryReadEvent interface", () => {
    const event: MemoryReadEvent = {
      ...makeBase("memory_read"),
      event_type: "memory_read",
      memory_layer: "episodic",
      query: "last task result",
      result_count: 3,
      cache_hit: true,
      backend: "sqlite",
      latency_ms: 12.5,
    };
    expect(event.memory_layer).toBe("episodic");
    expect(event.cache_hit).toBe(true);
  });

  it("should be identified by isMemoryReadEvent guard", () => {
    const event = {
      ...makeBase("memory_read"),
      event_type: "memory_read" as const,
      memory_layer: "semantic",
      query: "",
      result_count: 0,
      cache_hit: false,
      backend: "",
      latency_ms: 0,
    };
    expect(isMemoryReadEvent(event)).toBe(true);
  });
});

describe("MemoryWrittenEvent", () => {
  it("should satisfy the MemoryWrittenEvent interface", () => {
    const event: MemoryWrittenEvent = {
      ...makeBase("memory_written"),
      event_type: "memory_written",
      memory_id: "mem-001",
      memory_layer: "semantic",
      importance_score: 0.8,
      content_length: 256,
      backend: "redis",
    };
    expect(event.importance_score).toBe(0.8);
  });
});

// ---------------------------------------------------------------------------
// Delegation event type assertions
// ---------------------------------------------------------------------------

describe("DelegationRequestedEvent", () => {
  it("should satisfy the DelegationRequestedEvent interface", () => {
    const event: DelegationRequestedEvent = {
      ...makeBase("delegation_requested"),
      event_type: "delegation_requested",
      delegation_id: "del-001",
      target_agent_id: "sub-agent-1",
      task_description: "Summarize the document",
      priority: "normal",
      timeout_seconds: 60,
    };
    expect(event.target_agent_id).toBe("sub-agent-1");
  });

  it("should be identified by isDelegationRequestedEvent guard", () => {
    const event = {
      ...makeBase("delegation_requested"),
      event_type: "delegation_requested" as const,
      delegation_id: "",
      target_agent_id: "",
      task_description: "",
      priority: "normal",
      timeout_seconds: 0,
    };
    expect(isDelegationRequestedEvent(event)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Approval event type assertions
// ---------------------------------------------------------------------------

describe("ApprovalRequestedEvent", () => {
  it("should satisfy the ApprovalRequestedEvent interface", () => {
    const event: ApprovalRequestedEvent = {
      ...makeBase("approval_requested"),
      event_type: "approval_requested",
      approval_id: "apr-001",
      action_description: "Delete file /data/sensitive.csv",
      risk_level: "high",
      timeout_seconds: 300,
      requested_by: "agent-001",
    };
    expect(event.risk_level).toBe("high");
  });

  it("should be identified by isApprovalRequestedEvent guard", () => {
    const event = {
      ...makeBase("approval_requested"),
      event_type: "approval_requested" as const,
      approval_id: "",
      action_description: "",
      risk_level: "low",
      timeout_seconds: 0,
      requested_by: "",
    };
    expect(isApprovalRequestedEvent(event)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Identity type assertions
// ---------------------------------------------------------------------------

describe("AgentIdentity", () => {
  it("should satisfy the AgentIdentity interface", () => {
    const identity: AgentIdentity = {
      agent_id: "agent-xyz",
      name: "research-agent",
      version: "2.0.0",
      framework: "langchain",
      model: "claude-opus-4-6",
      created_at: "2024-01-01T00:00:00Z",
      metadata: { owner: "team-alpha" },
    };
    expect(identity.name).toBe("research-agent");
    expect(identity.framework).toBe("langchain");
  });
});

describe("TrustScore", () => {
  it("should satisfy the TrustScore interface", () => {
    const score: TrustScore = {
      agent_id: "agent-001",
      dimensions: {
        competence: 80,
        reliability: 75,
        integrity: 90,
      },
      composite: 81.67,
      level: "HIGH",
      timestamp: "2024-01-01T00:00:00Z",
    };
    expect(score.composite).toBeGreaterThan(0);
    expect(score.level).toBe("HIGH");
  });
});
