"""Benchmark: EventBus throughput and serialization.

Measures how many events can be published/dispatched per second and
how fast AgentEvent serialization runs.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType

_ITERATIONS: int = 10_000
_SERIALIZE_ITERATIONS: int = 20_000


def bench_event_bus_throughput() -> dict[str, object]:
    """Benchmark event publish throughput (sync emit_sync wrapper).

    Returns
    -------
    dict with keys: operation, iterations, total_seconds, ops_per_second,
    avg_latency_ms.
    """
    bus = EventBus(max_history=0)
    received: list[AgentEvent] = []
    bus.subscribe(EventType.AGENT_STARTED, received.append)

    async def _run() -> None:
        for _ in range(_ITERATIONS):
            evt = AgentEvent(EventType.AGENT_STARTED, "bench-agent")
            await bus.emit(evt)

    start = time.perf_counter()
    asyncio.run(_run())
    total = time.perf_counter() - start

    result: dict[str, object] = {
        "operation": "event_bus_throughput",
        "iterations": _ITERATIONS,
        "total_seconds": round(total, 4),
        "ops_per_second": round(_ITERATIONS / total, 1),
        "avg_latency_ms": round(total / _ITERATIONS * 1000, 4),
    }
    print(
        f"[bench_throughput] {result['operation']}: "
        f"{result['ops_per_second']:,.0f} ops/sec  "
        f"avg {result['avg_latency_ms']:.4f} ms"
    )
    return result


def bench_serialization_throughput() -> dict[str, object]:
    """Benchmark AgentEvent to_dict serialization throughput.

    Returns
    -------
    dict with keys: operation, iterations, total_seconds, ops_per_second,
    avg_latency_ms.
    """
    event = AgentEvent(
        event_type=EventType.TOOL_CALLED,
        agent_id="bench-agent",
        data={"tool": "search", "query": "test"},
    )

    start = time.perf_counter()
    for _ in range(_SERIALIZE_ITERATIONS):
        event.to_dict()
    total = time.perf_counter() - start

    result: dict[str, object] = {
        "operation": "agent_event_serialization",
        "iterations": _SERIALIZE_ITERATIONS,
        "total_seconds": round(total, 4),
        "ops_per_second": round(_SERIALIZE_ITERATIONS / total, 1),
        "avg_latency_ms": round(total / _SERIALIZE_ITERATIONS * 1000, 4),
    }
    print(
        f"[bench_throughput] {result['operation']}: "
        f"{result['ops_per_second']:,.0f} ops/sec  "
        f"avg {result['avg_latency_ms']:.4f} ms"
    )
    return result


if __name__ == "__main__":
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    for bench_fn, fname in [
        (bench_event_bus_throughput, "event_bus_throughput_baseline.json"),
        (bench_serialization_throughput, "serialization_throughput_baseline.json"),
    ]:
        result = bench_fn()
        output_path = results_dir / fname
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"Results saved to {output_path}")
