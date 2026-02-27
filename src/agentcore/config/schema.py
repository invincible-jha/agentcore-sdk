"""Config schema re-export and validation helpers for agentcore-sdk.

Re-exports ``AgentConfig`` from the canonical schema module so that
``agentcore.config`` is a complete import path for consumers who prefer
not to reach into ``agentcore.schema``.

Shipped in this module
----------------------
- AgentConfig     — re-export with full Pydantic v2 validation
- validate_config — standalone validation helper

Extension points
-------------------
Cross-field business rules, remote-schema validation, and versioned config
migration are available via plugins.
"""
from __future__ import annotations

from pydantic import ValidationError

from agentcore.schema.config import AgentConfig
from agentcore.schema.errors import ConfigurationError

__all__ = ["AgentConfig", "validate_config"]


def validate_config(data: dict[str, object]) -> AgentConfig:
    """Validate a raw dict against the ``AgentConfig`` schema.

    Parameters
    ----------
    data:
        Unvalidated key/value mapping.

    Returns
    -------
    AgentConfig
        Validated and typed configuration.

    Raises
    ------
    ConfigurationError
        If the data fails Pydantic validation.  The original
        ``ValidationError`` is attached as the ``__cause__``.

    Examples
    --------
    >>> validate_config({"agent_name": "bot"}).agent_name
    'bot'
    """
    try:
        return AgentConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError(
            f"Configuration validation failed: {exc}",
            context={"errors": exc.errors()},
        ) from exc
