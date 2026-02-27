"""Adapters package for agentcore-sdk.

Provides framework-specific adapters that intercept agent calls and emit
structured ``AgentEvent`` objects onto a shared ``EventBus``.
"""
from __future__ import annotations

from agentcore.adapters.anthropic_sdk import AnthropicAdapter
from agentcore.adapters.base import FrameworkAdapter
from agentcore.adapters.callable import CallableAdapter
from agentcore.adapters.crewai import CrewAIAdapter
from agentcore.adapters.langchain import LangChainAdapter
from agentcore.adapters.microsoft_agents import MicrosoftAgentAdapter
from agentcore.adapters.openai_agents import OpenAIAgentsAdapter

__all__ = [
    "FrameworkAdapter",
    "CallableAdapter",
    "LangChainAdapter",
    "CrewAIAdapter",
    "OpenAIAgentsAdapter",
    "AnthropicAdapter",
    "MicrosoftAgentAdapter",
]
