"""Benchmark: Memory usage of EventBus with event history."""
from __future__ import annotations

import asyncio
import json
import sys
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentcore.bus.event_bus import EventBus
from agentcore.schema.events import AgentEvent, EventType

_ITERATIONS: int = 1_000


def bench_event_bus_memory() -> dict[str, object]:
    """Benchmark memory usage of EventBus with history accumulation.

    Returns
    -------
    dict with keys: operation, iterations, peak_memory_kb, current_memory_kb.
    """
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    bus = EventBus(max_history=_ITERATIONS)

    async def _run() -> None:
        for i in range(_ITERATIONS):
            evt = AgentEvent(
                EventType.TOOL_CALLED,
                f"agent-{i}",
                data={"tool": "search", "query": f"query-{i}"},
            )
            await bus.emit(evt)

    asyncio.run(_run())

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_bytes = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
    peak_kb = round(total_bytes / 1024, 2)

    result: dict[str, object] = {
        "operation": "event_bus_memory",
        "iterations": _ITERATIONS,
        "peak_memory_kb": peak_kb,
        "current_memory_kb": peak_kb,
        "ops_per_second": 0.0,
        "avg_latency_ms": 0.0,
    }
    print(f"[bench_memory] {result['operation']}: peak {peak_kb:.2f} KB over {_ITERATIONS} iterations")
    return result


if __name__ == "__main__":
    result = bench_event_bus_memory()
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / "memory_baseline.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(f"Results saved to {output_path}")
