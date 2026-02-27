"""In-process metric collector for agentcore-sdk.

Provides a lightweight, allocation-efficient accumulator for named numeric
metrics with structured tags.  No external dependencies required.

Shipped in this module
----------------------
- MetricSummary   — aggregated stats for a single metric
- MetricCollector — accumulator for count, sum, min, max, avg

Extension points
-------------------
Histogram bucketing, percentile estimation (p50/p99), rolling-window
aggregation, and push-to-Prometheus adapters are available via plugins.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import NamedTuple


class _MetricKey(NamedTuple):
    """Internal composite key: metric name + frozen tag pairs."""

    name: str
    tags: tuple[tuple[str, str], ...]


@dataclass
class MetricSummary:
    """Aggregated statistics for a single (name, tags) combination.

    Attributes
    ----------
    name:
        Metric name, e.g. ``"tool_call_duration_ms"``.
    tags:
        Arbitrary key/value labels.
    count:
        Number of recorded observations.
    total:
        Sum of all observed values.
    minimum:
        Smallest observed value.
    maximum:
        Largest observed value.
    average:
        Arithmetic mean (``total / count``).
    """

    name: str
    tags: dict[str, str]
    count: int
    total: float
    minimum: float
    maximum: float
    average: float


@dataclass
class _Accumulator:
    """Mutable accumulator for a single metric key."""

    count: int = 0
    total: float = 0.0
    minimum: float = float("inf")
    maximum: float = float("-inf")

    def record(self, value: float) -> None:
        self.count += 1
        self.total += value
        if value < self.minimum:
            self.minimum = value
        if value > self.maximum:
            self.maximum = value

    @property
    def average(self) -> float:
        return self.total / self.count if self.count else 0.0


class MetricCollector:
    """Thread-safe in-memory metric accumulator.

    Records numeric observations keyed by metric name and optional string
    tags, accumulating count, sum, min, max, and average.

    Examples
    --------
    >>> collector = MetricCollector()
    >>> collector.record("latency_ms", 120.0, {"model": "gpt-4o"})
    >>> collector.record("latency_ms", 80.0, {"model": "gpt-4o"})
    >>> summary = collector.get_summary("latency_ms", {"model": "gpt-4o"})
    >>> summary.count
    2
    >>> summary.average
    100.0
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[_MetricKey, _Accumulator] = {}

    def record(
        self,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a single observation.

        Parameters
        ----------
        metric_name:
            Logical name for this metric series.
        value:
            Numeric observation to accumulate.
        tags:
            Optional string key/value labels that segment the series.
        """
        sorted_tags: tuple[tuple[str, str], ...] = tuple(
            sorted((tags or {}).items())
        )
        key = _MetricKey(name=metric_name, tags=sorted_tags)
        with self._lock:
            if key not in self._data:
                self._data[key] = _Accumulator()
            self._data[key].record(value)

    def get_summary(
        self,
        metric_name: str,
        tags: dict[str, str] | None = None,
    ) -> MetricSummary | None:
        """Return aggregated stats for a specific (name, tags) combination.

        Parameters
        ----------
        metric_name:
            The metric name to look up.
        tags:
            The tag set to match exactly.

        Returns
        -------
        MetricSummary | None
            ``None`` if no observations have been recorded for this key.
        """
        sorted_tags: tuple[tuple[str, str], ...] = tuple(
            sorted((tags or {}).items())
        )
        key = _MetricKey(name=metric_name, tags=sorted_tags)
        with self._lock:
            acc = self._data.get(key)
        if acc is None:
            return None
        return MetricSummary(
            name=metric_name,
            tags=dict(sorted_tags),
            count=acc.count,
            total=acc.total,
            minimum=acc.minimum if acc.count > 0 else 0.0,
            maximum=acc.maximum if acc.count > 0 else 0.0,
            average=acc.average,
        )

    def get_metrics(self) -> list[MetricSummary]:
        """Return summaries for every recorded (name, tags) combination.

        Returns
        -------
        list[MetricSummary]
            One entry per unique (name, tags) key.
        """
        with self._lock:
            snapshot = list(self._data.items())
        results: list[MetricSummary] = []
        for key, acc in snapshot:
            results.append(
                MetricSummary(
                    name=key.name,
                    tags=dict(key.tags),
                    count=acc.count,
                    total=acc.total,
                    minimum=acc.minimum if acc.count > 0 else 0.0,
                    maximum=acc.maximum if acc.count > 0 else 0.0,
                    average=acc.average,
                )
            )
        return results

    def reset(self) -> None:
        """Clear all accumulated metrics."""
        with self._lock:
            self._data.clear()

    def __repr__(self) -> str:
        with self._lock:
            series_count = len(self._data)
        return f"MetricCollector(series={series_count})"
