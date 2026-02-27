/**
 * TypeScript interfaces matching all Python event schemas from agentcore-sdk.
 *
 * These types mirror the Pydantic models defined in:
 *   - agentcore.schemas.lifecycle
 *   - agentcore.schemas.llm_events
 *   - agentcore.schemas.tool_events
 *   - agentcore.schemas.memory_events
 *   - agentcore.schemas.delegation_events
 *   - agentcore.schemas.approval_events
 *   - agentcore.schema.events (AgentEvent base)
 *
 * All interfaces use readonly fields to match Python's frozen Pydantic models.
 */

// ---------------------------------------------------------------------------
// Common base fields shared by all events
// ---------------------------------------------------------------------------

/** Fields present on every AEP-compliant event. */
export interface BaseAgentEvent {
  readonly event_id: string;
  readonly timestamp: string; // ISO-8601 UTC string
  readonly agent_id: string;
  readonly aep_version: string;
  readonly metadata: Readonly<Record<string, string>>;
}

// ---------------------------------------------------------------------------
// Lifecycle events (agentcore.schemas.lifecycle)
// ---------------------------------------------------------------------------

/** Emitted when an agent process transitions from idle to running. */
export interface AgentStartedEvent extends BaseAgentEvent {
  readonly event_type: "agent_started";
  readonly runtime: string;
  readonly entrypoint: string;
  readonly config_hash: string;
}

/** Emitted when an agent process finishes successfully. */
export interface AgentCompletedEvent extends BaseAgentEvent {
  readonly event_type: "agent_completed";
  readonly duration_ms: number;
  readonly output_summary: string;
  readonly total_cost_usd: number;
}

/** Emitted when an agent process terminates due to an unhandled error. */
export interface AgentFailedEvent extends BaseAgentEvent {
  readonly event_type: "agent_failed";
  readonly error_type: string;
  readonly error_message: string;
  readonly traceback: string;
  readonly duration_ms: number;
}

/** Emitted when an agent process suspends execution and awaits resumption. */
export interface AgentPausedEvent extends BaseAgentEvent {
  readonly event_type: "agent_paused";
  readonly pause_reason: string;
  readonly checkpoint_id: string;
  readonly awaiting_input: boolean;
}

/** Emitted when a paused agent process resumes execution. */
export interface AgentResumedEvent extends BaseAgentEvent {
  readonly event_type: "agent_resumed";
  readonly resumed_from_checkpoint: string;
  readonly pause_duration_ms: number;
  readonly resumed_by: string;
}

// ---------------------------------------------------------------------------
// LLM events (agentcore.schemas.llm_events)
// ---------------------------------------------------------------------------

/** Emitted immediately before an LLM API request is dispatched. */
export interface LLMCalledEvent extends BaseAgentEvent {
  readonly event_type: "llm_called";
  readonly call_id: string;
  readonly model_name: string;
  readonly provider: string;
  readonly prompt_tokens: number;
  readonly temperature: number;
  readonly max_tokens: number;
  readonly streaming: boolean;
}

/** Emitted when an LLM API request returns a complete non-streamed response. */
export interface LLMRespondedEvent extends BaseAgentEvent {
  readonly event_type: "llm_responded";
  readonly call_id: string;
  readonly model_name: string;
  readonly provider: string;
  readonly prompt_tokens: number;
  readonly completion_tokens: number;
  readonly total_tokens: number;
  readonly duration_ms: number;
  readonly finish_reason: string;
  readonly cost_usd: number;
}

/** Emitted for each token or token batch received from a streaming LLM call. */
export interface LLMStreamChunkEvent extends BaseAgentEvent {
  readonly event_type: "llm_stream_chunk";
  readonly call_id: string;
  readonly chunk_index: number;
  readonly delta: string;
  readonly is_final: boolean;
  readonly model_name: string;
}

// ---------------------------------------------------------------------------
// Tool events (agentcore.schemas.tool_events)
// ---------------------------------------------------------------------------

/** Emitted immediately before a tool is called. */
export interface ToolInvokedEvent extends BaseAgentEvent {
  readonly event_type: "tool_invoked";
  readonly tool_name: string;
  readonly tool_call_id: string;
  readonly input_schema: Readonly<Record<string, unknown>>;
  readonly input_values: Readonly<Record<string, unknown>>;
  readonly framework: string;
}

/** Emitted when a tool call completes successfully. */
export interface ToolCompletedEvent extends BaseAgentEvent {
  readonly event_type: "tool_completed";
  readonly tool_name: string;
  readonly tool_call_id: string;
  readonly duration_ms: number;
  readonly output_type: string;
  readonly truncated: boolean;
}

/** Emitted when a tool call raises an exception or returns an error. */
export interface ToolFailedEvent extends BaseAgentEvent {
  readonly event_type: "tool_failed";
  readonly tool_name: string;
  readonly tool_call_id: string;
  readonly error_type: string;
  readonly error_message: string;
  readonly recoverable: boolean;
  readonly duration_ms: number;
}

// ---------------------------------------------------------------------------
// Memory events (agentcore.schemas.memory_events)
// ---------------------------------------------------------------------------

/** Emitted when the agent reads one or more entries from memory. */
export interface MemoryReadEvent extends BaseAgentEvent {
  readonly event_type: "memory_read";
  readonly memory_layer: string;
  readonly query: string;
  readonly result_count: number;
  readonly cache_hit: boolean;
  readonly backend: string;
  readonly latency_ms: number;
}

/** Emitted when the agent writes a new entry to memory. */
export interface MemoryWrittenEvent extends BaseAgentEvent {
  readonly event_type: "memory_written";
  readonly memory_id: string;
  readonly memory_layer: string;
  readonly importance_score: number;
  readonly content_length: number;
  readonly backend: string;
}

/** Emitted when a memory entry is evicted from storage. */
export interface MemoryEvictedEvent extends BaseAgentEvent {
  readonly event_type: "memory_evicted";
  readonly memory_id: string;
  readonly memory_layer: string;
  readonly eviction_reason: string;
  readonly age_seconds: number;
}

// ---------------------------------------------------------------------------
// Delegation events (agentcore.schemas.delegation_events)
// ---------------------------------------------------------------------------

/** Emitted when an agent delegates a task to a sub-agent. */
export interface DelegationRequestedEvent extends BaseAgentEvent {
  readonly event_type: "delegation_requested";
  readonly delegation_id: string;
  readonly target_agent_id: string;
  readonly task_description: string;
  readonly priority: string;
  readonly timeout_seconds: number;
}

/** Emitted when the sub-agent completes a delegated task. */
export interface DelegationCompletedEvent extends BaseAgentEvent {
  readonly event_type: "delegation_completed";
  readonly delegation_id: string;
  readonly target_agent_id: string;
  readonly duration_ms: number;
  readonly success: boolean;
}

/** Emitted when a delegated task fails or is rejected. */
export interface DelegationFailedEvent extends BaseAgentEvent {
  readonly event_type: "delegation_failed";
  readonly delegation_id: string;
  readonly target_agent_id: string;
  readonly error_type: string;
  readonly error_message: string;
  readonly retryable: boolean;
}

// ---------------------------------------------------------------------------
// Human approval events (agentcore.schemas.approval_events)
// ---------------------------------------------------------------------------

/** Emitted when an agent requests human approval before proceeding. */
export interface ApprovalRequestedEvent extends BaseAgentEvent {
  readonly event_type: "approval_requested";
  readonly approval_id: string;
  readonly action_description: string;
  readonly risk_level: string;
  readonly timeout_seconds: number;
  readonly requested_by: string;
}

/** Emitted when a human approves or rejects the requested action. */
export interface ApprovalResolvedEvent extends BaseAgentEvent {
  readonly event_type: "approval_resolved";
  readonly approval_id: string;
  readonly approved: boolean;
  readonly reviewed_by: string;
  readonly review_comment: string;
  readonly resolution_latency_ms: number;
}

// ---------------------------------------------------------------------------
// Legacy base event (agentcore.schema.events)
// ---------------------------------------------------------------------------

/** Legacy base event type matching the AgentEvent dataclass. */
export interface AgentEventLegacy {
  readonly event_id: string;
  readonly event_type: string;
  readonly agent_id: string;
  readonly aep_version: string;
  readonly timestamp: string; // ISO-8601
  readonly data: Readonly<Record<string, unknown>>;
  readonly metadata: Readonly<Record<string, unknown>>;
  readonly parent_event_id: string | null;
}

/** Legacy tool call event matching ToolCallEvent dataclass. */
export interface ToolCallEventLegacy extends AgentEventLegacy {
  readonly tool_name: string;
  readonly tool_input: Readonly<Record<string, unknown>>;
  readonly tool_output: unknown;
}

/** Legacy decision event matching DecisionEvent dataclass. */
export interface DecisionEventLegacy extends AgentEventLegacy {
  readonly decision: string;
  readonly reasoning: string;
  readonly confidence: number | null;
}

// ---------------------------------------------------------------------------
// Union type of all canonical event types
// ---------------------------------------------------------------------------

/** Union of all known AEP event types. */
export type AnyAgentEvent =
  | AgentStartedEvent
  | AgentCompletedEvent
  | AgentFailedEvent
  | AgentPausedEvent
  | AgentResumedEvent
  | LLMCalledEvent
  | LLMRespondedEvent
  | LLMStreamChunkEvent
  | ToolInvokedEvent
  | ToolCompletedEvent
  | ToolFailedEvent
  | MemoryReadEvent
  | MemoryWrittenEvent
  | MemoryEvictedEvent
  | DelegationRequestedEvent
  | DelegationCompletedEvent
  | DelegationFailedEvent
  | ApprovalRequestedEvent
  | ApprovalResolvedEvent;

/** All canonical event_type literal strings. */
export type EventTypeLiteral =
  | "agent_started"
  | "agent_completed"
  | "agent_failed"
  | "agent_paused"
  | "agent_resumed"
  | "llm_called"
  | "llm_responded"
  | "llm_stream_chunk"
  | "tool_invoked"
  | "tool_completed"
  | "tool_failed"
  | "memory_read"
  | "memory_written"
  | "memory_evicted"
  | "delegation_requested"
  | "delegation_completed"
  | "delegation_failed"
  | "approval_requested"
  | "approval_resolved";

// ---------------------------------------------------------------------------
// Type guard helpers
// ---------------------------------------------------------------------------

/** Type guard: check if an event is an AgentStartedEvent. */
export function isAgentStartedEvent(event: BaseAgentEvent): event is AgentStartedEvent {
  return (event as AgentStartedEvent).event_type === "agent_started";
}

/** Type guard: check if an event is an LLMCalledEvent. */
export function isLLMCalledEvent(event: BaseAgentEvent): event is LLMCalledEvent {
  return (event as LLMCalledEvent).event_type === "llm_called";
}

/** Type guard: check if an event is an LLMRespondedEvent. */
export function isLLMRespondedEvent(event: BaseAgentEvent): event is LLMRespondedEvent {
  return (event as LLMRespondedEvent).event_type === "llm_responded";
}

/** Type guard: check if an event is a ToolInvokedEvent. */
export function isToolInvokedEvent(event: BaseAgentEvent): event is ToolInvokedEvent {
  return (event as ToolInvokedEvent).event_type === "tool_invoked";
}

/** Type guard: check if an event is a MemoryReadEvent. */
export function isMemoryReadEvent(event: BaseAgentEvent): event is MemoryReadEvent {
  return (event as MemoryReadEvent).event_type === "memory_read";
}

/** Type guard: check if an event is a DelegationRequestedEvent. */
export function isDelegationRequestedEvent(
  event: BaseAgentEvent
): event is DelegationRequestedEvent {
  return (event as DelegationRequestedEvent).event_type === "delegation_requested";
}

/** Type guard: check if an event is an ApprovalRequestedEvent. */
export function isApprovalRequestedEvent(
  event: BaseAgentEvent
): event is ApprovalRequestedEvent {
  return (event as ApprovalRequestedEvent).event_type === "approval_requested";
}
