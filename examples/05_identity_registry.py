#!/usr/bin/env python3
"""Example: Identity and Registry

Demonstrates DID-based agent identity creation, registration in
AgentRegistry, and health checking.

Usage:
    python examples/05_identity_registry.py

Requirements:
    pip install agentcore-sdk
"""
from __future__ import annotations

from agentcore import (
    create_identity,
    AgentRegistry,
    BasicIdentityProvider,
    AgentConfig,
    HealthCheck,
    HealthStatus,
)


def main() -> None:
    # Step 1: Create agent identities
    print("Creating agent identities:")
    identities = []
    for name in ["orchestrator", "researcher", "writer"]:
        identity = create_identity(agent_id=name, metadata={"role": name, "version": "1.0"})
        identities.append(identity)
        print(f"  [{name}] DID: {identity.did[:30]}...")

    # Step 2: Initialise an identity provider
    provider = BasicIdentityProvider()
    for identity in identities:
        provider.register(identity)
    print(f"\nIdentity provider: {provider.count()} identities registered")

    # Step 3: Resolve an identity
    resolved = provider.resolve("orchestrator")
    if resolved:
        print(f"Resolved 'orchestrator': did={resolved.did[:30]}... | metadata={resolved.metadata}")

    # Step 4: Create agent configs and register in registry
    registry = AgentRegistry()
    configs: list[AgentConfig] = [
        AgentConfig(
            agent_id=identity.agent_id,
            did=identity.did,
            capabilities=["search", "summarise"],
            metadata=identity.metadata,
        )
        for identity in identities
    ]

    for config in configs:
        registry.register(config)

    print(f"\nAgent registry: {registry.count()} agents")
    listed = registry.list()
    for agent_info in listed:
        print(f"  [{agent_info.agent_id}] capabilities={agent_info.capabilities}")

    # Step 5: Health check
    health_check = HealthCheck(components=["event_bus", "plugin_registry", "cost_tracker"])
    report = health_check.run()
    print(f"\nHealth report:")
    print(f"  Overall status: {report.overall.value}")
    for check in report.checks:
        status_icon = "OK" if check.status == HealthStatus.HEALTHY else "WARN"
        print(f"  [{status_icon}] {check.component}: {check.message}")


if __name__ == "__main__":
    main()
