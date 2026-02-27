# agentcore-sdk

**Agent Core SDK** — universal substrate for AI agent lifecycle management.

[![CI](https://github.com/invincible-jha/agentcore-sdk/actions/workflows/ci.yaml/badge.svg)](https://github.com/invincible-jha/agentcore-sdk/actions/workflows/ci.yaml)
[![PyPI version](https://img.shields.io/pypi/v/aumos-agentcore-sdk.svg)](https://pypi.org/project/aumos-agentcore-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/aumos-agentcore-sdk.svg)](https://pypi.org/project/aumos-agentcore-sdk/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/invincible-jha/agentcore-sdk/blob/main/LICENSE)

agentcore-sdk provides a canonical event taxonomy, thread-safe event bus, agent identity management, OpenTelemetry bridging, and a plugin registry — everything needed to instrument and manage AI agents in production without vendor lock-in.

## Installation

```bash
pip install aumos-agentcore-sdk
```

Verify the installation:

```bash
agentcore-sdk version
```

## Quick Start

```python
import agentcore
from agentcore.events import EventBus, AgentEvent, EventType
from agentcore.identity import AgentIdentity, IdentityRegistry

# Create an agent identity
identity = AgentIdentity(name="my-agent", version="1.0.0")
registry = IdentityRegistry()
registry.register(identity)

# Set up an event bus
bus = EventBus()

# Subscribe to all tool-call events
@bus.subscribe(EventType.TOOL_CALL)
def on_tool_call(event: AgentEvent) -> None:
    print(f"Tool called: {event.payload}")

# Publish an event
bus.publish(AgentEvent(
    event_type=EventType.TOOL_CALL,
    agent_id=identity.agent_id,
    payload={"tool": "search", "query": "agent lifecycle"},
))
```

## Key Features

- **Canonical event taxonomy** — `AgentEvent` covers started, stopped, tool call, decision, cost incurred, and more with full serde support and causal parent-event links
- **Thread-safe EventBus** — type-scoped and global subscriptions, configurable history buffer, and exception-safe async dispatch
- **Agent identity management** — `AgentIdentity` dataclass and `IdentityRegistry` for stable identity across restarts
- **OpenTelemetry bridge** — maps agent lifecycle events to OTel spans without requiring OTel to be installed
- **YAML config loader** — Pydantic v2 validation with environment-variable override support
- **Plugin architecture** — implement `AgentPlugin`, declare a Python entry-point, and the registry auto-discovers your plugin at startup
- **Framework adapters** — LangChain and CrewAI adapters translate framework-native events into `AgentEvent` payloads

## Links

- [GitHub Repository](https://github.com/invincible-jha/agentcore-sdk)
- [PyPI Package](https://pypi.org/project/aumos-agentcore-sdk/)
- [Architecture](architecture.md)
- [Contributing](https://github.com/invincible-jha/agentcore-sdk/blob/main/CONTRIBUTING.md)
- [Changelog](https://github.com/invincible-jha/agentcore-sdk/blob/main/CHANGELOG.md)

---

Part of the [AumOS](https://github.com/aumos-ai) open-source agent infrastructure portfolio.
