"""Telemetry exporter implementations for agentcore-sdk.

Exporters consume :class:`~agentcore.telemetry.collector.MetricSummary`
objects and ship them to a destination.  The abstraction allows the same
collection pipeline to target different backends with no code changes.

Shipped in this module
----------------------
- TelemetryExporter  — ABC for all exporters
- ConsoleExporter    — prints metrics to stdout via ``print``
- JSONFileExporter   — appends JSON Lines to a file
- NullExporter       — discards all data (no-op, useful in tests)

Withheld / internal
-------------------
Prometheus push-gateway, Datadog, New Relic, and CloudWatch exporters are
available via plugins.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from agentcore.telemetry.collector import MetricSummary


class TelemetryExporter(ABC):
    """Abstract base class for telemetry exporters."""

    @abstractmethod
    def export(self, summaries: list[MetricSummary]) -> None:
        """Export a batch of metric summaries to the target destination.

        Parameters
        ----------
        summaries:
            Metric summaries to export.  The list may be empty.
        """

    @abstractmethod
    def flush(self) -> None:
        """Ensure all buffered data has been written to the destination."""


class ConsoleExporter(TelemetryExporter):
    """Exporter that prints metric summaries to stdout.

    Primarily useful for local development and debugging.

    Examples
    --------
    >>> from agentcore.telemetry.collector import MetricSummary
    >>> exporter = ConsoleExporter()
    >>> exporter.export([])  # prints nothing for an empty list
    """

    def export(self, summaries: list[MetricSummary]) -> None:
        """Print each summary as a human-readable line."""
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        for summary in summaries:
            tag_str = ", ".join(f"{k}={v}" for k, v in summary.tags.items())
            tag_part = f" [{tag_str}]" if tag_str else ""
            print(
                f"[{timestamp}] metric={summary.name}{tag_part} "
                f"count={summary.count} avg={summary.average:.4f} "
                f"min={summary.minimum:.4f} max={summary.maximum:.4f} "
                f"total={summary.total:.4f}"
            )

    def flush(self) -> None:
        """No-op — stdout is line-buffered."""


class JSONFileExporter(TelemetryExporter):
    """Exporter that appends metric summaries as JSON Lines to a file.

    Each exported summary is written as a single JSON object on its own line
    (JSON Lines / NDJSON format).

    Parameters
    ----------
    file_path:
        Path to the output file.  Will be created if it does not exist.
    append:
        If ``True`` (default), new exports are appended to the existing
        file.  Set to ``False`` to truncate on each export call.

    Examples
    --------
    >>> import tempfile, pathlib
    >>> tmp = tempfile.mktemp(suffix=".jsonl")
    >>> exporter = JSONFileExporter(tmp)
    """

    def __init__(self, file_path: str | Path, *, append: bool = True) -> None:
        self._path = Path(file_path)
        self._mode = "a" if append else "w"

    def export(self, summaries: list[MetricSummary]) -> None:
        """Append *summaries* to the JSON Lines file."""
        if not summaries:
            return
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        with self._path.open(self._mode, encoding="utf-8") as fh:
            for summary in summaries:
                record = {
                    "timestamp": timestamp,
                    "name": summary.name,
                    "tags": summary.tags,
                    "count": summary.count,
                    "total": summary.total,
                    "minimum": summary.minimum,
                    "maximum": summary.maximum,
                    "average": summary.average,
                }
                fh.write(json.dumps(record) + "\n")

    def flush(self) -> None:
        """No-op — file handle is closed after each export batch."""


class NullExporter(TelemetryExporter):
    """Exporter that silently discards all metric summaries.

    Useful in tests, or when telemetry emission is disabled at config level.
    """

    def export(self, summaries: list[MetricSummary]) -> None:
        """Discard *summaries* without side effects."""

    def flush(self) -> None:
        """No-op."""
