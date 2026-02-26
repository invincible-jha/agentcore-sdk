"""Adapters package for agentcore-sdk.

Provides framework-specific adapters that intercept agent calls and emit
structured ``AgentEvent`` objects onto a shared ``EventBus``.
"""
from __future__ import annotations

from agentcore.adapters.base import FrameworkAdapter
from agentcore.adapters.callable import CallableAdapter
from agentcore.adapters.crewai import CrewAIAdapter
from agentcore.adapters.langchain import LangChainAdapter

__all__ = [
    "FrameworkAdapter",
    "CallableAdapter",
    "LangChainAdapter",
    "CrewAIAdapter",
]
