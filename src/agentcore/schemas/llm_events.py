"""LLM event schemas — call, response, stream chunk.

These events capture the interaction boundary with the language model provider.
They are emitted by the agent runtime around each LLM API invocation.

All models are frozen Pydantic BaseModels.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# LLMCalledEvent
# ---------------------------------------------------------------------------


class LLMCalledEvent(BaseModel):
    """Emitted immediately before an LLM API request is dispatched.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Identifier of the agent making the request.
    event_type:
        Always ``"llm_called"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    call_id:
        Unique identifier for this LLM invocation; correlates with the
        corresponding ``LLMRespondedEvent`` or stream chunks.
    model_name:
        Provider-agnostic model identifier (e.g. ``"gpt-4o"``).
    provider:
        Name of the LLM provider (e.g. ``"openai"``, ``"anthropic"``).
    prompt_tokens:
        Estimated number of tokens in the prompt, if pre-calculated.
    temperature:
        Sampling temperature used for this request.
    max_tokens:
        Maximum tokens allowed in the response.
    streaming:
        Whether the response will be delivered as a stream.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["llm_called"] = "llm_called"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    call_id: str = Field(default_factory=_new_uuid)
    model_name: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    temperature: float = 1.0
    max_tokens: int = 0
    streaming: bool = False


# ---------------------------------------------------------------------------
# LLMRespondedEvent
# ---------------------------------------------------------------------------


class LLMRespondedEvent(BaseModel):
    """Emitted when an LLM API request returns a complete (non-streamed) response.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the event was emitted.
    agent_id:
        Identifier of the agent that made the request.
    event_type:
        Always ``"llm_responded"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    call_id:
        Matches the ``call_id`` from the corresponding ``LLMCalledEvent``.
    model_name:
        Provider-agnostic model identifier.
    provider:
        Name of the LLM provider.
    prompt_tokens:
        Actual number of tokens in the prompt as reported by the provider.
    completion_tokens:
        Number of tokens in the completion as reported by the provider.
    total_tokens:
        Sum of prompt and completion tokens.
    duration_ms:
        Wall-clock time from request dispatch to response receipt (ms).
    finish_reason:
        Provider finish reason (e.g. ``"stop"``, ``"length"``).
    cost_usd:
        Estimated cost of this API call in USD.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["llm_responded"] = "llm_responded"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    call_id: str = ""
    model_name: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0
    finish_reason: str = "stop"
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# LLMStreamChunkEvent
# ---------------------------------------------------------------------------


class LLMStreamChunkEvent(BaseModel):
    """Emitted for each token or token batch received from a streaming LLM call.

    Stream chunks are produced at high frequency; consumers that only need
    final results should subscribe to ``LLMRespondedEvent`` instead.

    Attributes
    ----------
    event_id:
        Globally unique event identifier.
    timestamp:
        UTC time at which the chunk was received.
    agent_id:
        Identifier of the agent receiving the stream.
    event_type:
        Always ``"llm_stream_chunk"``.
    aep_version:
        AEP specification version in use.
    metadata:
        Arbitrary cross-cutting annotations.
    call_id:
        Matches the ``call_id`` from the corresponding ``LLMCalledEvent``.
    chunk_index:
        Zero-based sequential position of this chunk within the stream.
    delta:
        The incremental text content of this chunk.
    is_final:
        True for the last chunk in the stream; false for all others.
    model_name:
        Provider-agnostic model identifier.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=_new_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    agent_id: str
    event_type: Literal["llm_stream_chunk"] = "llm_stream_chunk"
    aep_version: str = "1.0.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    call_id: str = ""
    chunk_index: int = 0
    delta: str = ""
    is_final: bool = False
    model_name: str = ""
