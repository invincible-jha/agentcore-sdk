/**
 * @aumos/agentcore
 *
 * TypeScript client for the AumOS agentcore-sdk.
 * Provides HTTP client, event builders, type definitions, and identity interfaces
 * that mirror the Python agentcore-sdk schema contracts.
 *
 * The client is now backed by @aumos/sdk-core for automatic retry,
 * typed error hierarchy, and request lifecycle events.
 */

// --- Client and configuration ---
export type {
  AgentcoreClient,
  AgentcoreClientConfig,
  EmitEventRequest,
  EmitEventResponse,
  HistoryQueryOptions,
} from "./client.js";
export { createAgentcoreClient } from "./client.js";

// --- Core types (ApiResult, AgentEvent, AgentConfig, plugin/bus types) ---
export type {
  ApiError,
  ApiResult,
  EventType,
  AgentEvent,
  ToolCallEvent,
  DecisionEvent,
  AgentConfig,
  AgentConfigInput,
  PluginDescriptor,
  PluginListResult,
  EventSubscription,
  EventBusStatus,
} from "./types.js";

// --- Full event schema catalogue (lifecycle, LLM, tool, memory, delegation, approval) ---
export type {
  // Base
  BaseAgentEvent,
  AnyAgentEvent,
  EventTypeLiteral,
  AgentEventLegacy,
  ToolCallEventLegacy,
  DecisionEventLegacy,

  // Lifecycle events
  AgentStartedEvent,
  AgentCompletedEvent,
  AgentFailedEvent,
  AgentPausedEvent,
  AgentResumedEvent,

  // LLM events
  LLMCalledEvent,
  LLMRespondedEvent,
  LLMStreamChunkEvent,

  // Tool events
  ToolInvokedEvent,
  ToolCompletedEvent,
  ToolFailedEvent,

  // Memory events
  MemoryReadEvent,
  MemoryWrittenEvent,
  MemoryEvictedEvent,

  // Delegation events
  DelegationRequestedEvent,
  DelegationCompletedEvent,
  DelegationFailedEvent,

  // Approval events
  ApprovalRequestedEvent,
  ApprovalResolvedEvent,
} from "./events.js";

// Type guard functions
export {
  isAgentStartedEvent,
  isLLMCalledEvent,
  isLLMRespondedEvent,
  isToolInvokedEvent,
  isMemoryReadEvent,
  isDelegationRequestedEvent,
  isApprovalRequestedEvent,
} from "./events.js";

// --- Identity interfaces (AgentIdentity, trust scoring, DID, certs, delegation) ---
export type {
  AgentIdentity,
  TrustDimension,
  TrustDimensions,
  TrustLevel,
  TrustScore,
  AgentIdentityRecord,
  DIDVerificationMethod,
  DIDDocument,
  DIDServiceEndpoint,
  AgentCertificate,
  DelegationToken,
  VerifyRequest,
  VerifyResponse,
} from "./identity.js";

// --- Re-export sdk-core error hierarchy for callers that want to instanceof-check ---
export {
  AumosError,
  NetworkError,
  TimeoutError,
  HttpError,
  RateLimitError,
  ValidationError,
  ServerError,
  AbortError,
} from "@aumos/sdk-core";

// --- Re-export event emitter type for listeners attached via client.events ---
export type { SdkEventEmitter, SdkEventMap } from "@aumos/sdk-core";
