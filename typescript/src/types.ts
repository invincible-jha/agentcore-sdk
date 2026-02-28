/**
 * Core type definitions for the @aumos/agentcore package.
 *
 * Contains:
 *   - ApiResult<T> discriminated union (shared pattern across all @aumos packages)
 *   - AgentConfig — validated runtime configuration type
 *   - EventType — canonical event type taxonomy
 *   - PluginDescriptor / PluginListResult — plugin registry types
 *   - EventBusStatus / EventSubscription — event bus introspection types
 *   - AgentEvent / ToolCallEvent / DecisionEvent — base event envelope types
 *   - AgentIdentityBasic — simplified identity for config use
 *
 * Mirrors the Python types defined in:
 *   agentcore.schema.events   — EventType, AgentEvent, ToolCallEvent, DecisionEvent
 *   agentcore.schema.config   — AgentConfig
 *   agentcore.plugins.registry — PluginRegistry, AgentPluginRegistry
 *   agentcore.bus.event_bus   — EventBus
 *
 * All interfaces use readonly fields to match Python's frozen/dataclass patterns.
 */

// ---------------------------------------------------------------------------
// Shared API result wrapper (consistent across all @aumos packages)
// ---------------------------------------------------------------------------

/** Standard error payload returned by the agentcore HTTP API. */
export interface ApiError {
  readonly error: string;
  readonly detail: string;
}

/**
 * Discriminated union result type for all client operations.
 *
 * @example
 * ```ts
 * const result = await client.getIdentity("agent-42");
 * if (result.ok) {
 *   console.log(result.data.name);
 * } else {
 *   console.error(result.error.detail);
 * }
 * ```
 */
export type ApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: ApiError; readonly status: number };

// ---------------------------------------------------------------------------
// EventType — canonical taxonomy
// ---------------------------------------------------------------------------

/**
 * Canonical taxonomy of agent lifecycle event types.
 * Maps to EventType(str, Enum) in the Python agentcore.schema.events module.
 *
 * Using a string union (not a const enum) preserves tree-shaking
 * and allows JSON round-trips without extra serialisation steps.
 */
export type EventType =
  | "agent_started"
  | "agent_stopped"
  | "tool_called"
  | "tool_completed"
  | "tool_failed"
  | "decision_made"
  | "message_received"
  | "message_sent"
  | "error_occurred"
  | "cost_incurred"
  | "custom";

// ---------------------------------------------------------------------------
// AgentEvent — base event envelope (AEP-001)
// ---------------------------------------------------------------------------

/**
 * Base event carrying all fields common to every agent lifecycle signal.
 * Mirrors the AgentEvent dataclass in Python.
 *
 * Complies with the Agent Event Protocol (AEP) specification v1.0.0.
 * See AEP-001 for the full event envelope contract.
 */
export interface AgentEvent {
  /** Globally unique event identifier (UUID4). Auto-generated if absent. */
  readonly event_id: string;
  /** One of the canonical EventType values. */
  readonly event_type: EventType;
  /** Stable identifier for the agent that emitted this event. */
  readonly agent_id: string;
  /** ISO-8601 UTC timestamp of when the event was created. */
  readonly timestamp: string;
  /** Agent Event Protocol version string (semver). Defaults to "1.0.0". */
  readonly aep_version: string;
  /** Arbitrary payload specific to this event. Values must be JSON-safe. */
  readonly data: Readonly<Record<string, unknown>>;
  /** Cross-cutting concerns: trace IDs, tags, environment labels, etc. */
  readonly metadata: Readonly<Record<string, unknown>>;
  /** Optional causal link to a parent event (supports event chains). */
  readonly parent_event_id: string | null;
}

/**
 * Specialised event for tool invocations.
 * Extends AgentEvent with tool_name, tool_input, and tool_output fields.
 * Mirrors the ToolCallEvent dataclass in Python.
 */
export interface ToolCallEvent extends AgentEvent {
  /** Must be a tool-related event type. */
  readonly event_type: "tool_called" | "tool_completed" | "tool_failed";
  /** The canonical name of the tool that was called. */
  readonly tool_name: string;
  /** The arguments passed to the tool. */
  readonly tool_input: Readonly<Record<string, unknown>>;
  /** The result returned by the tool; null for TOOL_CALLED events. */
  readonly tool_output: unknown | null;
}

/**
 * Specialised event for agent decision points.
 * Extends AgentEvent with decision, reasoning, and confidence fields.
 * Mirrors the DecisionEvent dataclass in Python.
 */
export interface DecisionEvent extends AgentEvent {
  /** Must be the decision_made event type. */
  readonly event_type: "decision_made";
  /** Short label describing the decision that was made. */
  readonly decision: string;
  /** Free-text explanation of why this decision was taken. */
  readonly reasoning: string;
  /** Score in [0.0, 1.0]; null if the framework does not expose confidence. */
  readonly confidence: number | null;
}

// ---------------------------------------------------------------------------
// AgentConfig — validated runtime configuration
// ---------------------------------------------------------------------------

/**
 * Validated runtime configuration for an agentcore-powered agent.
 * Mirrors the AgentConfig Pydantic model in Python.
 *
 * All fields have sensible defaults so that an agent can start with zero
 * configuration and progressively opt-in to features.
 */
export interface AgentConfig {
  /** Human-readable agent name. Defaults to "unnamed-agent". */
  readonly agent_name: string;
  /** SemVer version string. Defaults to "0.1.0". */
  readonly agent_version: string;
  /** Agent framework identifier (e.g. "langchain", "crewai"). */
  readonly framework: string;
  /** Primary LLM identifier (e.g. "claude-sonnet-4-6"). */
  readonly model: string;
  /** Whether OpenTelemetry spans and metrics are emitted. */
  readonly telemetry_enabled: boolean;
  /** Whether token-cost accounting is active. */
  readonly cost_tracking_enabled: boolean;
  /** Whether the event bus is active. */
  readonly event_bus_enabled: boolean;
  /** Plugin names to auto-load at startup. */
  readonly plugins: readonly string[];
  /** Arbitrary key/value store for framework-specific or user settings. */
  readonly custom_settings: Readonly<Record<string, unknown>>;
}

/** Partial config for creating or updating an AgentConfig via the API. */
export type AgentConfigInput = Partial<
  Omit<AgentConfig, "plugins" | "custom_settings">
> & {
  readonly plugins?: readonly string[];
  readonly custom_settings?: Readonly<Record<string, unknown>>;
};

// ---------------------------------------------------------------------------
// Plugin registry types (from agentcore.plugins.registry)
// ---------------------------------------------------------------------------

/**
 * Descriptor for a registered plugin in the agentcore plugin registry.
 * Derived from PluginRegistry and AgentPluginRegistry in Python.
 */
export interface PluginDescriptor {
  /** The unique string key for this plugin. */
  readonly name: string;
  /** Human-readable description of what this plugin does. */
  readonly description: string;
  /** SemVer string for the plugin's release. */
  readonly version: string;
  /** Whether the plugin has been successfully initialized. */
  readonly initialized: boolean;
}

/** Result of a plugin discovery or listing operation. */
export interface PluginListResult {
  /** All registered plugin names, sorted alphabetically. */
  readonly plugin_names: readonly string[];
  /** Total count of registered plugins. */
  readonly count: number;
}

// ---------------------------------------------------------------------------
// EventBus interface types (from agentcore.bus.event_bus)
// ---------------------------------------------------------------------------

/**
 * Subscription handle returned by EventBus subscribe operations.
 * Pass the subscription_id to the unsubscribe endpoint to cancel.
 */
export interface EventSubscription {
  /** Opaque subscription ID (UUID4). */
  readonly subscription_id: string;
  /** The EventType this subscription is scoped to, or "all" for global. */
  readonly event_type: EventType | "all";
}

/** Snapshot of EventBus state from the server introspection endpoint. */
export interface EventBusStatus {
  /** Total number of active subscriptions. */
  readonly subscriber_count: number;
  /** Number of events currently in the history buffer. */
  readonly history_size: number;
  /** Maximum history buffer capacity (0 = disabled). */
  readonly max_history: number;
}
