/**
 * HTTP client for the agentcore-sdk server API.
 *
 * Uses the Fetch API (available natively in Node 18+, browsers, and Deno).
 * No external dependencies required.
 *
 * @example
 * ```ts
 * import { createAgentcoreClient } from "@aumos/agentcore";
 *
 * const client = createAgentcoreClient({ baseUrl: "http://localhost:8080" });
 *
 * // Register a new agent identity
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
// Internal helpers
// ---------------------------------------------------------------------------

async function fetchJson<T>(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    clearTimeout(timeoutId);

    const body = (await response.json()) as unknown;

    if (!response.ok) {
      const errorBody = body as Partial<ApiError>;
      return {
        ok: false,
        error: {
          error: errorBody.error ?? "Unknown error",
          detail: errorBody.detail ?? "",
        },
        status: response.status,
      };
    }

    return { ok: true, data: body as T };
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    const message = err instanceof Error ? err.message : String(err);
    return {
      ok: false,
      error: { error: "Network error", detail: message },
      status: 0,
    };
  }
}

function buildHeaders(
  extraHeaders: Readonly<Record<string, string>> | undefined,
): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...extraHeaders,
  };
}

// ---------------------------------------------------------------------------
// Client interface
// ---------------------------------------------------------------------------

/** Typed HTTP client for the agentcore-sdk server. */
export interface AgentcoreClient {
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
 * @param config - Client configuration including base URL.
 * @returns An AgentcoreClient instance backed by the Fetch API.
 */
export function createAgentcoreClient(
  config: AgentcoreClientConfig,
): AgentcoreClient {
  const { baseUrl, timeoutMs = 30_000, headers: extraHeaders } = config;
  const baseHeaders = buildHeaders(extraHeaders);

  return {
    // --- Identity management ---

    async createIdentity(
      agentConfig: AgentConfig,
    ): Promise<ApiResult<AgentIdentity>> {
      return fetchJson<AgentIdentity>(
        `${baseUrl}/agents`,
        {
          method: "POST",
          headers: baseHeaders,
          body: JSON.stringify(agentConfig),
        },
        timeoutMs,
      );
    },

    async getIdentity(agentId: string): Promise<ApiResult<AgentIdentity>> {
      return fetchJson<AgentIdentity>(
        `${baseUrl}/agents/${encodeURIComponent(agentId)}`,
        { method: "GET", headers: baseHeaders },
        timeoutMs,
      );
    },

    async updateConfig(
      agentId: string,
      updates: AgentConfigInput,
    ): Promise<ApiResult<AgentConfig>> {
      return fetchJson<AgentConfig>(
        `${baseUrl}/agents/${encodeURIComponent(agentId)}/config`,
        {
          method: "PATCH",
          headers: baseHeaders,
          body: JSON.stringify(updates),
        },
        timeoutMs,
      );
    },

    async getConfig(agentId: string): Promise<ApiResult<AgentConfig>> {
      return fetchJson<AgentConfig>(
        `${baseUrl}/agents/${encodeURIComponent(agentId)}/config`,
        { method: "GET", headers: baseHeaders },
        timeoutMs,
      );
    },

    // --- Event bus ---

    async emitEvent(
      event: AgentEvent,
    ): Promise<ApiResult<EmitEventResponse>> {
      return fetchJson<EmitEventResponse>(
        `${baseUrl}/events`,
        {
          method: "POST",
          headers: baseHeaders,
          body: JSON.stringify(event),
        },
        timeoutMs,
      );
    },

    async getHistory(
      options: HistoryQueryOptions = {},
    ): Promise<ApiResult<readonly AnyAgentEvent[]>> {
      const params = new URLSearchParams();
      if (options.agentId !== undefined) {
        params.set("agent_id", options.agentId);
      }
      if (options.eventType !== undefined) {
        params.set("event_type", options.eventType);
      }
      if (options.limit !== undefined) {
        params.set("limit", String(options.limit));
      }
      const queryString = params.toString();
      const url = queryString
        ? `${baseUrl}/events/history?${queryString}`
        : `${baseUrl}/events/history`;
      return fetchJson<readonly AnyAgentEvent[]>(
        url,
        { method: "GET", headers: baseHeaders },
        timeoutMs,
      );
    },

    async getBusStatus(): Promise<ApiResult<EventBusStatus>> {
      return fetchJson<EventBusStatus>(
        `${baseUrl}/events/bus/status`,
        { method: "GET", headers: baseHeaders },
        timeoutMs,
      );
    },

    // --- Plugin registry ---

    async listPlugins(): Promise<ApiResult<PluginListResult>> {
      return fetchJson<PluginListResult>(
        `${baseUrl}/plugins`,
        { method: "GET", headers: baseHeaders },
        timeoutMs,
      );
    },

    async getPlugin(pluginName: string): Promise<ApiResult<PluginDescriptor>> {
      return fetchJson<PluginDescriptor>(
        `${baseUrl}/plugins/${encodeURIComponent(pluginName)}`,
        { method: "GET", headers: baseHeaders },
        timeoutMs,
      );
    },

    async discoverPlugins(): Promise<ApiResult<PluginListResult>> {
      return fetchJson<PluginListResult>(
        `${baseUrl}/plugins/discover`,
        { method: "POST", headers: baseHeaders },
        timeoutMs,
      );
    },

    // --- Subscriptions ---

    async subscribe(options: {
      eventType: EventType | "all";
      webhookUrl: string;
    }): Promise<ApiResult<EventSubscription>> {
      return fetchJson<EventSubscription>(
        `${baseUrl}/events/subscriptions`,
        {
          method: "POST",
          headers: baseHeaders,
          body: JSON.stringify({
            event_type: options.eventType,
            webhook_url: options.webhookUrl,
          }),
        },
        timeoutMs,
      );
    },

    async unsubscribe(
      subscriptionId: string,
    ): Promise<ApiResult<Record<string, never>>> {
      return fetchJson<Record<string, never>>(
        `${baseUrl}/events/subscriptions/${encodeURIComponent(subscriptionId)}`,
        { method: "DELETE", headers: baseHeaders },
        timeoutMs,
      );
    },
  };
}

/** Re-export request/response types for convenience. */
export type {
  AgentConfig,
  AgentConfigInput,
  AgentEvent,
  EmitEventRequest,
  EmitEventResponse,
  EventBusStatus,
  EventSubscription,
  EventType,
  HistoryQueryOptions,
  PluginDescriptor,
  PluginListResult,
};
