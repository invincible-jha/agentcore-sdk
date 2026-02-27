"""Model pricing catalogue for agentcore-sdk.

Public pricing is crowd-sourced and updated to the best of our knowledge.
Prices are expressed in USD per 1 000 tokens.  Negotiated or volume pricing
is not reflected here.

Shipped in this module
----------------------
- PricingEntry    — named tuple for a single model's pricing
- MODEL_PRICING   — dict mapping canonical model IDs to PricingEntry
- get_pricing()   — resolve a model ID to its PricingEntry, with fuzzy match

Extension points
-------------------
Real-time pricing API polling, volume-tier discounts, and multi-currency
support are available via plugins.
"""
from __future__ import annotations

from typing import NamedTuple


class PricingEntry(NamedTuple):
    """Pricing for a single model.

    Attributes
    ----------
    input_cost_per_1k:
        USD cost per 1 000 input tokens.
    output_cost_per_1k:
        USD cost per 1 000 output tokens.
    """

    input_cost_per_1k: float
    output_cost_per_1k: float


# ---------------------------------------------------------------------------
# Pricing table — USD per 1 000 tokens (as of February 2026, best-effort)
# ---------------------------------------------------------------------------
MODEL_PRICING: dict[str, PricingEntry] = {
    # Anthropic Claude
    "claude-opus-4": PricingEntry(input_cost_per_1k=0.015, output_cost_per_1k=0.075),
    "claude-sonnet-4-5": PricingEntry(input_cost_per_1k=0.003, output_cost_per_1k=0.015),
    "claude-haiku-4-5": PricingEntry(input_cost_per_1k=0.00025, output_cost_per_1k=0.00125),
    # OpenAI GPT
    "gpt-4o": PricingEntry(input_cost_per_1k=0.005, output_cost_per_1k=0.015),
    "gpt-4o-mini": PricingEntry(input_cost_per_1k=0.00015, output_cost_per_1k=0.0006),
    "gpt-3.5-turbo": PricingEntry(input_cost_per_1k=0.0005, output_cost_per_1k=0.0015),
    # Google Gemini
    "gemini-1.5-pro": PricingEntry(input_cost_per_1k=0.00125, output_cost_per_1k=0.005),
    "gemini-1.5-flash": PricingEntry(input_cost_per_1k=0.000075, output_cost_per_1k=0.0003),
    # Meta / open-weight
    "llama-3.1-70b": PricingEntry(input_cost_per_1k=0.00059, output_cost_per_1k=0.00079),
    # Mistral
    "mistral-large": PricingEntry(input_cost_per_1k=0.004, output_cost_per_1k=0.012),
}

# Build a lower-cased alias index for fuzzy matching
_MODEL_ALIAS_INDEX: dict[str, str] = {k.lower(): k for k in MODEL_PRICING}


def get_pricing(model: str) -> PricingEntry | None:
    """Resolve a model identifier to its :class:`PricingEntry`.

    Lookup is case-insensitive.  If an exact match is not found, fuzzy
    matching checks whether the provided string is a *prefix* of a known
    model ID (e.g. ``"claude-sonnet"`` resolves to ``"claude-sonnet-4-5"``).
    The first alphabetical match wins on ambiguity.

    Parameters
    ----------
    model:
        Model identifier string.

    Returns
    -------
    PricingEntry | None
        ``None`` if no matching entry is found.

    Examples
    --------
    >>> entry = get_pricing("gpt-4o")
    >>> entry.input_cost_per_1k
    0.005
    >>> get_pricing("unknown-model-xyz") is None
    True
    """
    normalised = model.lower()

    # Exact match first
    if normalised in _MODEL_ALIAS_INDEX:
        return MODEL_PRICING[_MODEL_ALIAS_INDEX[normalised]]

    # Prefix fuzzy match
    candidates = [
        canonical
        for alias, canonical in _MODEL_ALIAS_INDEX.items()
        if alias.startswith(normalised) or normalised.startswith(alias)
    ]
    if candidates:
        return MODEL_PRICING[sorted(candidates)[0]]

    return None
