# Examples

| # | Example | Description |
|---|---------|-------------|
| 01 | [Quickstart](01_quickstart.py) | Minimal working example with AgentCore and EventBus |
| 02 | [Event Bus](02_event_bus.py) | Typed subscriptions, filters, and event delivery |
| 03 | [Plugin Registry](03_plugin_registry.py) | Register, discover, and use custom plugins |
| 04 | [Cost Tracking](04_cost_tracking.py) | Track LLM spend with CostTracker and BudgetManager |
| 05 | [Identity Registry](05_identity_registry.py) | DID-based identity creation and agent registry |
| 06 | [LangChain Integration](06_langchain_integration.py) | Bridge agentcore EventBus into LangChain callbacks |
| 07 | [Multi-Agent](07_multi_agent.py) | Coordinate multiple agents via shared EventBus |

## Running the examples

```bash
pip install agentcore-sdk
python examples/01_quickstart.py
```

For framework integrations:

```bash
pip install langchain langchain-openai   # for example 06
```
