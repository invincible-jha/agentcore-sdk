/**
 * HTTP client for the agentcore-sdk server API.
 *
 * Backed by @aumos/sdk-core's createHttpClient which provides automatic retry
 * with exponential backoff, typed error hierarchy, request lifecycle events,
 * and abort signal support.
 *
 * The public API surface is unchanged — all methods still return ApiResult<T>
 * so existing callers require no migration work.
 *
 * @example
 * ```ts
 * import { createAgentcoreClient } from "@aumos/agentcore";
 *
 * const client = createAgentcoreClient({ baseUrl: "http://localhost:8080" });
 *
 * const identity = await client.createIdentity({
 *   agent_name: "research-agent",
 *   agent_version: "1.0.0",
 *   framework: "langchain",
 *   model: "claude-sonnet-4-6",
 *   telemetry_enabled: true,
 *   cost_tracking_enabled: true,
 *   event_bus_enabled: true,
 *   plugins: [],
 *   custom_settings: {},
 * });
 *
 * if (identity.ok) {
 *   console.log("Agent registered:", identity.data.agent_id);
 * }
 * ```
 */

import {
  createHttpClient,
  HttpError,
  NetworkError,
  TimeoutError,
  RateLimitError,
  ServerError,
  ValidationError,
  AumosError,
} from "@aumos/sdk-core";

import type { HttpClient, SdkEventEmitter } from "@aumos/sdk-core";

import type {
  AgentConfig,
  AgentConfigInput,
  AgentEvent,
  ApiError,
  ApiResult,
  EventBusStatus,
  EventSubscription,
  EventType,
  PluginDescriptor,
  PluginListResult,
} from "./types.js";

import type { AgentIdentity } from "./identity.js";
import type { AnyAgentEvent } from "./events.js";

// ---------------------------------------------------------------------------
// Client configuration
// ---------------------------------------------------------------------------

/** Configuration options for the AgentcoreClient. */
export interface AgentcoreClientConfig {
  /** Base URL of the agentcore server (e.g. "http://localhost:8080"). */
  readonly baseUrl: string;
  /** Optional request timeout in milliseconds. Defaults to 30000. */
  readonly timeoutMs?: number;
  /** Optional extra HTTP headers sent with every request. */
  readonly headers?: Readonly<Record<string, string>>;
  /** Optional maximum retry count. Defaults to 3. */
  readonly maxRetries?: number;
}

// ---------------------------------------------------------------------------
// Event emit request
// ---------------------------------------------------------------------------

/** Request body for emitting an event to the agentcore event bus. */
export interface EmitEventRequest {
  /** The event to emit. Must be a valid AgentEvent envelope. */
  readonly event: AgentEvent;
}

/** Response from the event emit endpoint. */
export interface EmitEventResponse {
  /** Whether the event was accepted and dispatched. */
  readonly accepted: boolean;
  /** The event_id of the dispatched event. */
  readonly event_id: string;
  /** Number of subscribers that received the event. */
  readonly dispatch_count: number;
}

// ---------------------------------------------------------------------------
// History query options
// ---------------------------------------------------------------------------

/** Options for querying the event bus history. */
export interface HistoryQueryOptions {
  /** Filter events by agent ID. */
  readonly agentId?: string;
  /** Filter events to a specific event type. */
  readonly eventType?: EventType;
  /** Maximum number of events to return. Defaults to 100. */
  readonly limit?: number;
}

// ---------------------------------------------------------------------------
// Internal adapter — bridges HttpClient throws into ApiResult<T>
// ---------------------------------------------------------------------------

/**
 * Converts a structured api error body to the canonical ApiError shape.
 * Handles both full {error, detail} bodies and plain string messages.
 */
function extractApiError(body: unknown, fallbackMessage: string): ApiError {
  if (
    body !== null &&
    typeof body === "object" &&
    "error" in body &&
    typeof (body as Record<string, unknown>)["error"] === "string"
  ) {
    const candidate = body as Partial<{ error: string; detail: string }>;
    return {
      error: candidate.error ?? fallbackMessage,
      detail: candidate.detail ?? "",
    };
  }
  return { error: fallbackMessage, detail: "" };
}

/**
 * Wraps an sdk-core HttpClient call, translating thrown AumosError instances
 * into the ApiResult<T> discriminated-union format.
 *
 * This adapter preserves 100% backward compatibility: existing callers that
 * pattern-match on { ok, data } / { ok, error, status } continue to work.
 * New callers can additionally attach listeners to `client.events` for
 * structured retry / lifecycle observability.
 */
async function executeApiCall<T>(
  call: () => Promise<T>,
): Promise<ApiResult<T>> {
  try {
    const data = await call();
    return { ok: true, data };
  } catch (error: unknown) {
    if (error instanceof RateLimitError) {
      return {
        ok: false,
        error: extractApiError(error.body, "Rate limit exceeded"),
        status: 429,
      };
    }
    if (error instanceof ValidationError) {
      return {
        ok: false,
        error: {
          error: "Validation failed",
          detail: Object.entries(error.fields)
            .map(([field, messages]) => `${field}: ${messages.join(", ")}`)
            .join("; "),
        },
        status: 422,
      };
    }
    if (error instanceof ServerError) {
      return {
        ok: false,
        error: extractApiError(error.body, `Server error: HTTP ${error.statusCode}`),
        status: error.statusCode,
      };
    }
    if (error instanceof HttpError) {
      return {
        ok: false,
        error: extractApiError(error.body, `HTTP error: ${error.statusCode}`),
        status: error.statusCode,
      };
    }
    if (error instanceof TimeoutError) {
      return {
        ok: false,
        error: { error: "Request timed out", detail: error.message },
        status: 0,
      };
    }
    if (error instanceof NetworkError) {
      return {
        ok: false,
        error: {
          error: "Network error",
          detail: error instanceof Error ? error.message : String(error),
        },
        status: 0,
      };
    }
    if (error instanceof AumosError) {
      return {
        ok: false,
        error: { error: error.code, detail: error.message },
        status: error.statusCode ?? 0,
      };
    }
    // Unknown errors — surface generically
    const message = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      error: { error: "Unknown error", detail: message },
      status: 0,
    };
  }
}

// ---------------------------------------------------------------------------
// Client interface
// ---------------------------------------------------------------------------

/** Typed HTTP client for the agentcore-sdk server. */
export interface AgentcoreClient {
  /**
   * Typed event emitter exposed from the underlying sdk-core HttpClient.
   * Attach listeners here to observe request lifecycle, retries, and errors.
   *
   * @example
   * ```ts
   * client.events.on("request:retry", ({ payload }) => {
   *   console.warn(`Retry attempt ${payload.attempt}, delay ${payload.delayMs}ms`);
   * });
   * ```
   */
  readonly events: SdkEventEmitter;

  // --- Identity management ---

  /**
   * Register a new agent with the agentcore server.
   *
   * @param config - Agent configuration including name, version, framework, and model.
   * @returns The created AgentIdentity with auto-generated agent_id.
   */
  createIdentity(config: AgentConfig): Promise<ApiResult<AgentIdentity>>;

  /**
   * Retrieve the identity record for a specific agent.
   *
   * @param agentId - The stable agent identifier.
   * @returns The AgentIdentity record if found.
   */
  getIdentity(agentId: string): Promise<ApiResult<AgentIdentity>>;

  /**
   * Update an existing agent's configuration.
   *
   * @param agentId - The stable agent identifier.
   * @param updates - Partial configuration fields to update.
   * @returns The updated AgentConfig.
   */
  updateConfig(
    agentId: string,
    updates: AgentConfigInput,
  ): Promise<ApiResult<AgentConfig>>;

  /**
   * Retrieve the current runtime configuration for an agent.
   *
   * @param agentId - The stable agent identifier.
   * @returns The agent's AgentConfig.
   */
  getConfig(agentId: string): Promise<ApiResult<AgentConfig>>;

  // --- Event bus ---

  /**
   * Emit an event to the agentcore event bus.
   *
   * @param event - The AgentEvent to dispatch to all subscribers.
   * @returns EmitEventResponse with dispatch statistics.
   */
  emitEvent(event: AgentEvent): Promise<ApiResult<EmitEventResponse>>;

  /**
   * Retrieve event history from the server-side history buffer.
   *
   * @param options - Optional filters for agent ID, event type, and result count.
   * @returns Array of events in emission order, oldest first.
   */
  getHistory(
    options?: HistoryQueryOptions,
  ): Promise<ApiResult<readonly AnyAgentEvent[]>>;

  /**
   * Retrieve the current status of the agentcore event bus.
   *
   * @returns EventBusStatus with subscriber count and history size.
   */
  getBusStatus(): Promise<ApiResult<EventBusStatus>>;

  // --- Plugin registry ---

  /**
   * List all registered plugins in the agentcore plugin registry.
   *
   * @returns PluginListResult with sorted plugin names and total count.
   */
  listPlugins(): Promise<ApiResult<PluginListResult>>;

  /**
   * Retrieve the descriptor for a specific registered plugin.
   *
   * @param pluginName - The unique plugin identifier.
   * @returns PluginDescriptor if the plugin is registered.
   */
  getPlugin(pluginName: string): Promise<ApiResult<PluginDescriptor>>;

  /**
   * Trigger auto-discovery of plugins via entry-point scanning on the server.
   *
   * @returns PluginListResult listing newly discovered plugins.
   */
  discoverPlugins(): Promise<ApiResult<PluginListResult>>;

  // --- Subscriptions (server-sent or webhook registration) ---

  /**
   * Register a webhook URL to receive events matching a given type.
   *
   * @param options - Event type to subscribe to, and target webhook URL.
   * @returns EventSubscription with the opaque subscription ID.
   */
  subscribe(options: {
    eventType: EventType | "all";
    webhookUrl: string;
  }): Promise<ApiResult<EventSubscription>>;

  /**
   * Cancel a previously registered event subscription.
   *
   * @param subscriptionId - The ID returned by subscribe().
   * @returns Empty success or an error if the ID is not found.
   */
  unsubscribe(subscriptionId: string): Promise<ApiResult<Record<string, never>>>;
}

// ---------------------------------------------------------------------------
// Client factory
// ---------------------------------------------------------------------------

/**
 * Create a typed HTTP client for the agentcore-sdk server.
 *
 * Internally uses @aumos/sdk-core's createHttpClient for automatic retry,
 * typed errors, and request lifecycle events. The public API remains identical
 * to the previous version — all methods return ApiResult<T>.
 *
 * @param config - Client configuration including base URL.
 * @returns An AgentcoreClient instance.
 */
export function createAgentcoreClient(
  config: AgentcoreClientConfig,
): AgentcoreClient {
  const httpClient: HttpClient = createHttpClient({
    baseUrl: config.baseUrl,
    timeout: config.timeoutMs ?? 30_000,
    maxRetries: config.maxRetries ?? 3,
    defaultHeaders: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(config.headers as Record<string, string> | undefined),
    },
  });

  return {
    events: httpClient.events,

    // --- Identity management ---

    createIdentity(
      agentConfig: AgentConfig,
    ): Promise<ApiResult<AgentIdentity>> {
      return executeApiCall(() =>
        httpClient.post<AgentIdentity>("/agents", agentConfig).then((r) => r.data),
      );
    },

    getIdentity(agentId: string): Promise<ApiResult<AgentIdentity>> {
      return executeApiCall(() =>
        httpClient
          .get<AgentIdentity>(`/agents/${encodeURIComponent(agentId)}`)
          .then((r) => r.data),
      );
    },

    updateConfig(
      agentId: string,
      updates: AgentConfigInput,
    ): Promise<ApiResult<AgentConfig>> {
      return executeApiCall(() =>
        httpClient
          .patch<AgentConfig>(
            `/agents/${encodeURIComponent(agentId)}/config`,
            updates,
          )
          .then((r) => r.data),
      );
    },

    getConfig(agentId: string): Promise<ApiResult<AgentConfig>> {
      return executeApiCall(() =>
        httpClient
          .get<AgentConfig>(`/agents/${encodeURIComponent(agentId)}/config`)
          .then((r) => r.data),
      );
    },

    // --- Event bus ---

    emitEvent(event: AgentEvent): Promise<ApiResult<EmitEventResponse>> {
      return executeApiCall(() =>
        httpClient
          .post<EmitEventResponse>("/events", event)
          .then((r) => r.data),
      );
    },

    getHistory(
      options: HistoryQueryOptions = {},
    ): Promise<ApiResult<readonly AnyAgentEvent[]>> {
      const queryParams: Record<string, string> = {};
      if (options.agentId !== undefined) {
        queryParams["agent_id"] = options.agentId;
      }
      if (options.eventType !== undefined) {
        queryParams["event_type"] = options.eventType;
      }
      if (options.limit !== undefined) {
        queryParams["limit"] = String(options.limit);
      }

      return executeApiCall(() =>
        httpClient
          .get<readonly AnyAgentEvent[]>("/events/history", { queryParams })
          .then((r) => r.data),
      );
    },

    getBusStatus(): Promise<ApiResult<EventBusStatus>> {
      return executeApiCall(() =>
        httpClient
          .get<EventBusStatus>("/events/bus/status")
          .then((r) => r.data),
      );
    },

    // --- Plugin registry ---

    listPlugins(): Promise<ApiResult<PluginListResult>> {
      return executeApiCall(() =>
        httpClient.get<PluginListResult>("/plugins").then((r) => r.data),
      );
    },

    getPlugin(pluginName: string): Promise<ApiResult<PluginDescriptor>> {
      return executeApiCall(() =>
        httpClient
          .get<PluginDescriptor>(`/plugins/${encodeURIComponent(pluginName)}`)
          .then((r) => r.data),
      );
    },

    discoverPlugins(): Promise<ApiResult<PluginListResult>> {
      return executeApiCall(() =>
        httpClient
          .post<PluginListResult>("/plugins/discover")
          .then((r) => r.data),
      );
    },

    // --- Subscriptions ---

    subscribe(options: {
      eventType: EventType | "all";
      webhookUrl: string;
    }): Promise<ApiResult<EventSubscription>> {
      return executeApiCall(() =>
        httpClient
          .post<EventSubscription>("/events/subscriptions", {
            event_type: options.eventType,
            webhook_url: options.webhookUrl,
          })
          .then((r) => r.data),
      );
    },

    unsubscribe(
      subscriptionId: string,
    ): Promise<ApiResult<Record<string, never>>> {
      return executeApiCall(() =>
        httpClient
          .delete<Record<string, never>>(
            `/events/subscriptions/${encodeURIComponent(subscriptionId)}`,
          )
          .then((r) => r.data),
      );
    },
  };
}
