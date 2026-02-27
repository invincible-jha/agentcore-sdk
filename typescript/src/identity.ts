/**
 * TypeScript interfaces for agent identity and trust, matching the Python
 * schemas from agentcore.schema.identity and agent-identity.
 */

// ---------------------------------------------------------------------------
// Core agent identity
// ---------------------------------------------------------------------------

/** Stable, serialisable identity for an AumOS agent. */
export interface AgentIdentity {
  readonly agent_id: string;
  readonly name: string;
  readonly version: string;
  readonly framework: string;
  readonly model: string;
  readonly created_at: string; // ISO-8601 UTC string
  readonly metadata: Readonly<Record<string, unknown>>;
}

// ---------------------------------------------------------------------------
// Trust scoring
// ---------------------------------------------------------------------------

/** Trust dimension identifiers — matches TrustDimension enum in Python. */
export type TrustDimension = "competence" | "reliability" | "integrity";

/** Per-dimension trust scores (0–100 range). */
export type TrustDimensions = Readonly<Record<TrustDimension, number>>;

/** Trust level names — matches TrustLevel enum in Python. */
export type TrustLevel =
  | "UNTRUSTED"
  | "LOW"
  | "MEDIUM"
  | "HIGH"
  | "VERIFIED";

/** Computed trust score for a single agent at a point in time. */
export interface TrustScore {
  readonly agent_id: string;
  readonly dimensions: TrustDimensions;
  readonly composite: number;
  readonly level: TrustLevel;
  readonly timestamp: string; // ISO-8601 UTC string
}

// ---------------------------------------------------------------------------
// Identity registry records
// ---------------------------------------------------------------------------

/** Full identity record as stored in the agent-identity registry. */
export interface AgentIdentityRecord {
  readonly agent_id: string;
  readonly display_name: string;
  readonly organization: string;
  readonly capabilities: readonly string[];
  readonly metadata: Readonly<Record<string, unknown>>;
  readonly did: string;
  readonly registered_at: string; // ISO-8601 UTC string
  readonly updated_at: string; // ISO-8601 UTC string
  readonly active: boolean;
}

// ---------------------------------------------------------------------------
// DID (Decentralized Identifier) support
// ---------------------------------------------------------------------------

/** Verification method in a DID Document. */
export interface DIDVerificationMethod {
  readonly id: string;
  readonly type: string;
  readonly controller: string;
  readonly public_key_multibase?: string;
}

/** A minimal DID Document structure. */
export interface DIDDocument {
  readonly "@context": readonly string[];
  readonly id: string;
  readonly verification_method: readonly DIDVerificationMethod[];
  readonly authentication: readonly string[];
  readonly capability_invocation: readonly string[];
  readonly service: readonly DIDServiceEndpoint[];
  readonly created: string; // ISO-8601 UTC string
  readonly updated: string; // ISO-8601 UTC string
}

/** A service endpoint declared in a DID Document. */
export interface DIDServiceEndpoint {
  readonly id: string;
  readonly type: string;
  readonly service_endpoint: string;
}

// ---------------------------------------------------------------------------
// Certificate and delegation
// ---------------------------------------------------------------------------

/** Agent certificate for cryptographic identity verification. */
export interface AgentCertificate {
  readonly cert_id: string;
  readonly agent_id: string;
  readonly issuer: string;
  readonly subject: string;
  readonly not_before: string; // ISO-8601 UTC string
  readonly not_after: string; // ISO-8601 UTC string
  readonly capabilities: readonly string[];
  readonly signature: string;
  readonly revoked: boolean;
}

/** Delegation token granting one agent authority to act for another. */
export interface DelegationToken {
  readonly token_id: string;
  readonly delegator_id: string;
  readonly delegatee_id: string;
  readonly capabilities: readonly string[];
  readonly issued_at: string; // ISO-8601 UTC string
  readonly expires_at: string; // ISO-8601 UTC string
  readonly revoked: boolean;
  readonly context: Readonly<Record<string, string>>;
}

// ---------------------------------------------------------------------------
// Verification requests and responses
// ---------------------------------------------------------------------------

/** Request to verify an agent's identity and claimed capabilities. */
export interface VerifyRequest {
  readonly agent_id: string;
  readonly claimed_capabilities: readonly string[];
  readonly context: Readonly<Record<string, string>>;
}

/** Result of an identity verification check. */
export interface VerifyResponse {
  readonly agent_id: string;
  readonly verified: boolean;
  readonly active: boolean;
  readonly capabilities_valid: boolean;
  readonly missing_capabilities: readonly string[];
  readonly trust_score: number | null;
  readonly message: string;
}
