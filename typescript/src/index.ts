/**
 * @aumos/agentcore-types — TypeScript type definitions for AumOS AgentCore SDK.
 *
 * Provides TypeScript interfaces matching all Python event schemas and
 * identity structures from the agentcore-sdk and agent-identity packages.
 */

// Event interfaces and type guards
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

// Identity interfaces
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
