# agentcore-sdk

Agent substrate: event schemas, identity, telemetry bridge, plugin registry

[![CI](https://github.com/aumos-ai/agentcore-sdk/actions/workflows/ci.yaml/badge.svg)](https://github.com/aumos-ai/agentcore-sdk/actions/workflows/ci.yaml)
[![PyPI version](https://img.shields.io/pypi/v/agentcore-sdk.svg)](https://pypi.org/project/agentcore-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/agentcore-sdk.svg)](https://pypi.org/project/agentcore-sdk/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Part of the [AumOS](https://github.com/aumos-ai) open-source agent infrastructure portfolio.

---

## Features

- Canonical `AgentEvent` taxonomy (started, stopped, tool call, decision, cost incurred, and more) with full serde support and causal parent-event links
- Thread-safe in-process `EventBus` with type-scoped and global subscriptions, configurable history buffer, and exception-safe async dispatch
- `AgentIdentity` dataclass and `IdentityRegistry` for stable agent identity across restarts
- OpenTelemetry bridge that maps agent lifecycle events to OTel spans without requiring OTel to be installed
- YAML-driven config loader with Pydantic v2 validation and environment-variable override support
- Extensible plugin architecture via Python entry-points — implement `AgentPlugin`, declare an entry-point, and the registry auto-discovers your plugin at startup
- Adapters for LangChain and CrewAI that translate framework-native events into `AgentEvent` payloads

## Quick Start

Install from PyPI:

```bash
pip install agentcore-sdk
```

Verify the installation:

```bash
agentcore-sdk version
```

Basic usage:

```python
import agentcore

# See examples/01_quickstart.py for a working example
```

## Documentation

- [Architecture](docs/architecture.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Examples](examples/README.md)

## Enterprise Upgrade

For production deployments requiring SLA-backed support and advanced
integrations, contact the maintainers or see the commercial extensions documentation.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md)
before opening a pull request.

## License

Apache 2.0 — see [LICENSE](LICENSE) for full terms.

---

Part of [AumOS](https://github.com/aumos-ai) — open-source agent infrastructure.
