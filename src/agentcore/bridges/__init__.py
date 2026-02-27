"""Framework bridge adapters subpackage.

Bridges map third-party framework events (LangChain callbacks, CrewAI task
events, AutoGen messages) into standard :class:`~agentcore.schema.events.AgentEvent`
objects and emit them on an :class:`~agentcore.bus.event_bus.EventBus`.
"""
from __future__ import annotations

from agentcore.bridges.base import FrameworkBridge
from agentcore.bridges.langchain_bridge import LangChainBridge
from agentcore.bridges.crewai_bridge import CrewAIBridge
from agentcore.bridges.autogen_bridge import AutoGenBridge

__all__ = [
    "AutoGenBridge",
    "CrewAIBridge",
    "FrameworkBridge",
    "LangChainBridge",
]
