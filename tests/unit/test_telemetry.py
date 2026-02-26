"""Unit tests for agentcore.telemetry — collector, exporter, and otel_bridge."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentcore.schema.events import AgentEvent, EventType
from agentcore.telemetry.collector import MetricCollector, MetricSummary, _Accumulator
from agentcore.telemetry.exporter import (
    ConsoleExporter,
    JSONFileExporter,
    NullExporter,
)
from agentcore.telemetry.otel_bridge import OTelBridge


# ---------------------------------------------------------------------------
# _Accumulator (internal)
# ---------------------------------------------------------------------------

class TestAccumulator:
    def test_record_single_value(self) -> None:
        acc = _Accumulator()
        acc.record(10.0)
        assert acc.count == 1
        assert acc.total == 10.0
        assert acc.minimum == 10.0
        assert acc.maximum == 10.0

    def test_record_multiple_values_min_max_avg(self) -> None:
        acc = _Accumulator()
        for v in [5.0, 10.0, 15.0]:
            acc.record(v)
        assert acc.minimum == 5.0
        assert acc.maximum == 15.0
        assert acc.average == pytest.approx(10.0)

    def test_average_zero_when_no_records(self) -> None:
        acc = _Accumulator()
        assert acc.average == 0.0


# ---------------------------------------------------------------------------
# MetricCollector
# ---------------------------------------------------------------------------

class TestMetricCollector:
    def test_record_and_get_summary(self) -> None:
        collector = MetricCollector()
        collector.record("latency", 100.0)
        summary = collector.get_summary("latency")
        assert summary is not None
        assert summary.count == 1
        assert summary.total == 100.0

    def test_get_summary_returns_none_for_unknown_metric(self) -> None:
        collector = MetricCollector()
        assert collector.get_summary("ghost-metric") is None

    def test_record_with_tags_segments_series(self) -> None:
        collector = MetricCollector()
        collector.record("latency", 50.0, {"model": "gpt-4o"})
        collector.record("latency", 80.0, {"model": "claude-opus-4"})

        s1 = collector.get_summary("latency", {"model": "gpt-4o"})
        s2 = collector.get_summary("latency", {"model": "claude-opus-4"})
        assert s1 is not None and s1.average == pytest.approx(50.0)
        assert s2 is not None and s2.average == pytest.approx(80.0)

    def test_tags_order_is_normalised(self) -> None:
        collector = MetricCollector()
        collector.record("m", 1.0, {"b": "2", "a": "1"})
        collector.record("m", 3.0, {"a": "1", "b": "2"})
        summary = collector.get_summary("m", {"a": "1", "b": "2"})
        assert summary is not None
        assert summary.count == 2

    def test_get_metrics_returns_all_series(self) -> None:
        collector = MetricCollector()
        collector.record("a", 1.0)
        collector.record("b", 2.0)
        summaries = collector.get_metrics()
        names = {s.name for s in summaries}
        assert {"a", "b"} <= names

    def test_reset_clears_all_data(self) -> None:
        collector = MetricCollector()
        collector.record("x", 99.0)
        collector.reset()
        assert collector.get_summary("x") is None
        assert collector.get_metrics() == []

    def test_repr_contains_series_count(self) -> None:
        collector = MetricCollector()
        collector.record("m", 1.0)
        assert "series=1" in repr(collector)

    def test_summary_min_max_zero_when_no_records(self) -> None:
        collector = MetricCollector()
        collector.record("fresh", 42.0)
        summary = collector.get_summary("fresh")
        assert summary is not None
        assert summary.minimum == 42.0
        assert summary.maximum == 42.0

    def test_metric_summary_fields(self) -> None:
        collector = MetricCollector()
        collector.record("m", 10.0, {"env": "test"})
        collector.record("m", 20.0, {"env": "test"})
        s = collector.get_summary("m", {"env": "test"})
        assert s is not None
        assert s.name == "m"
        assert s.tags == {"env": "test"}
        assert s.count == 2
        assert s.total == pytest.approx(30.0)
        assert s.minimum == pytest.approx(10.0)
        assert s.maximum == pytest.approx(20.0)
        assert s.average == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# ConsoleExporter
# ---------------------------------------------------------------------------

class TestConsoleExporter:
    def test_export_empty_list_does_not_print(self, capsys: pytest.CaptureFixture[str]) -> None:
        exporter = ConsoleExporter()
        exporter.export([])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_export_one_summary_prints_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        exporter = ConsoleExporter()
        summary = MetricSummary(
            name="test_metric",
            tags={"model": "gpt-4o"},
            count=5,
            total=500.0,
            minimum=80.0,
            maximum=120.0,
            average=100.0,
        )
        exporter.export([summary])
        captured = capsys.readouterr()
        assert "test_metric" in captured.out
        assert "model=gpt-4o" in captured.out
        assert "count=5" in captured.out

    def test_export_summary_without_tags(self, capsys: pytest.CaptureFixture[str]) -> None:
        exporter = ConsoleExporter()
        summary = MetricSummary(
            name="no_tags",
            tags={},
            count=1,
            total=10.0,
            minimum=10.0,
            maximum=10.0,
            average=10.0,
        )
        exporter.export([summary])
        captured = capsys.readouterr()
        assert "no_tags" in captured.out

    def test_flush_is_noop(self) -> None:
        exporter = ConsoleExporter()
        exporter.flush()  # must not raise


# ---------------------------------------------------------------------------
# JSONFileExporter
# ---------------------------------------------------------------------------

class TestJSONFileExporter:
    def _make_summary(self, name: str = "m", value: float = 10.0) -> MetricSummary:
        return MetricSummary(
            name=name,
            tags={},
            count=1,
            total=value,
            minimum=value,
            maximum=value,
            average=value,
        )

    def test_export_writes_jsonl(self, tmp_path: Path) -> None:
        out_file = tmp_path / "metrics.jsonl"
        exporter = JSONFileExporter(out_file)
        exporter.export([self._make_summary("m1"), self._make_summary("m2")])

        lines = out_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        record = json.loads(lines[0])
        assert "name" in record
        assert "timestamp" in record

    def test_export_empty_list_does_not_write_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "empty.jsonl"
        exporter = JSONFileExporter(out_file)
        exporter.export([])
        assert not out_file.exists()

    def test_append_mode_accumulates(self, tmp_path: Path) -> None:
        out_file = tmp_path / "app.jsonl"
        exporter = JSONFileExporter(out_file, append=True)
        exporter.export([self._make_summary("first")])
        exporter.export([self._make_summary("second")])
        lines = out_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_non_append_mode_overwrites(self, tmp_path: Path) -> None:
        out_file = tmp_path / "over.jsonl"
        exporter = JSONFileExporter(out_file, append=False)
        exporter.export([self._make_summary("first")])
        exporter.export([self._make_summary("second")])
        lines = out_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["name"] == "second"

    def test_flush_is_noop(self, tmp_path: Path) -> None:
        exporter = JSONFileExporter(tmp_path / "f.jsonl")
        exporter.flush()  # must not raise

    def test_export_record_contains_all_fields(self, tmp_path: Path) -> None:
        out_file = tmp_path / "fields.jsonl"
        exporter = JSONFileExporter(out_file)
        summary = MetricSummary(
            name="full",
            tags={"k": "v"},
            count=3,
            total=30.0,
            minimum=5.0,
            maximum=15.0,
            average=10.0,
        )
        exporter.export([summary])
        record = json.loads(out_file.read_text(encoding="utf-8").strip())
        for key in ("name", "tags", "count", "total", "minimum", "maximum", "average", "timestamp"):
            assert key in record


# ---------------------------------------------------------------------------
# NullExporter
# ---------------------------------------------------------------------------

class TestNullExporter:
    def test_export_is_noop(self) -> None:
        exporter = NullExporter()
        summary = MetricSummary(
            name="m", tags={}, count=1, total=1.0, minimum=1.0, maximum=1.0, average=1.0
        )
        exporter.export([summary])  # must not raise

    def test_flush_is_noop(self) -> None:
        exporter = NullExporter()
        exporter.flush()  # must not raise


# ---------------------------------------------------------------------------
# OTelBridge — no-op mode (otel not installed in test env)
# ---------------------------------------------------------------------------

class TestOTelBridgeNoOp:
    def test_is_available_false_without_otel(self) -> None:
        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", False):
            bridge = OTelBridge()
            assert bridge.is_available() is False

    def test_start_span_returns_none_when_otel_absent(self) -> None:
        bridge = OTelBridge()
        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", False):
            bridge._tracer = None
            event = AgentEvent(EventType.AGENT_STARTED, "agent-1")
            result = bridge.start_span(event)
        assert result is None

    def test_end_span_with_none_key_is_safe(self) -> None:
        bridge = OTelBridge()
        bridge.end_span(None)  # must not raise

    def test_record_event_is_noop_when_otel_absent(self) -> None:
        bridge = OTelBridge()
        bridge._event_counter = None
        event = AgentEvent(EventType.AGENT_STARTED, "agent-1")
        bridge.record_event(event)  # must not raise

    def test_record_metric_is_noop_when_otel_absent(self) -> None:
        bridge = OTelBridge()
        bridge._meter = None
        bridge.record_metric("my.metric", 1.5, {"k": "v"})  # must not raise

    def test_flush_is_noop_when_otel_absent(self) -> None:
        bridge = OTelBridge()
        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", False):
            bridge.flush()  # must not raise

    def test_translate_event_is_noop_when_otel_absent(self) -> None:
        bridge = OTelBridge()
        bridge._tracer = None
        bridge._event_counter = None
        event = AgentEvent(EventType.TOOL_CALLED, "agent-1")
        bridge.translate_event(event)  # must not raise


class TestOTelBridgeWithMockedOTel:
    """Tests that exercise OTelBridge with the otel API mocked."""

    def _make_bridge_with_mock_otel(self) -> tuple[OTelBridge, MagicMock, MagicMock]:
        mock_tracer = MagicMock()
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_span = MagicMock()

        mock_tracer.start_span.return_value = mock_span
        mock_meter.create_counter.return_value = mock_counter

        bridge = OTelBridge()
        bridge._tracer = mock_tracer
        bridge._meter = mock_meter
        bridge._event_counter = mock_counter

        return bridge, mock_tracer, mock_counter

    def test_start_span_stores_active_span(self) -> None:
        bridge, mock_tracer, _ = self._make_bridge_with_mock_otel()
        event = AgentEvent(EventType.AGENT_STARTED, "agent-x")

        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", True):
            span_key = bridge.start_span(event)

        assert span_key is not None
        assert span_key in bridge._active_spans

    def test_end_span_calls_span_end(self) -> None:
        bridge, mock_tracer, _ = self._make_bridge_with_mock_otel()
        mock_span = MagicMock()
        bridge._active_spans["test-key"] = mock_span

        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", True):
            bridge.end_span("test-key")

        mock_span.end.assert_called_once()
        assert "test-key" not in bridge._active_spans

    def test_record_event_increments_counter(self) -> None:
        bridge, _, mock_counter = self._make_bridge_with_mock_otel()
        event = AgentEvent(EventType.TOOL_CALLED, "agent-x")

        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", True):
            bridge.record_event(event)

        mock_counter.add.assert_called_once()

    def test_record_metric_creates_histogram(self) -> None:
        bridge, _, _ = self._make_bridge_with_mock_otel()
        mock_histogram = MagicMock()
        bridge._meter.create_histogram.return_value = mock_histogram

        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", True):
            bridge.record_metric("latency", 42.5, {"model": "gpt-4o"})

        bridge._meter.create_histogram.assert_called_once()
        mock_histogram.record.assert_called_once_with(42.5, attributes={"model": "gpt-4o"})

    def test_flush_calls_force_flush(self) -> None:
        bridge, _, _ = self._make_bridge_with_mock_otel()
        mock_provider = MagicMock()
        mock_provider.force_flush = MagicMock()

        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", True):
            with patch("agentcore.telemetry.otel_bridge.otel_trace") as mock_trace_mod:
                mock_trace_mod.get_tracer_provider.return_value = mock_provider
                bridge.flush()

        mock_provider.force_flush.assert_called_once()

    def test_flush_swallows_exception(self) -> None:
        bridge, _, _ = self._make_bridge_with_mock_otel()

        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", True):
            with patch("agentcore.telemetry.otel_bridge.otel_trace") as mock_trace_mod:
                mock_trace_mod.get_tracer_provider.side_effect = RuntimeError("provider error")
                bridge.flush()  # must not raise

    def test_translate_event_full_pipeline(self) -> None:
        bridge, mock_tracer, mock_counter = self._make_bridge_with_mock_otel()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        event = AgentEvent(EventType.AGENT_STOPPED, "agent-z")

        with patch("agentcore.telemetry.otel_bridge._OTEL_AVAILABLE", True):
            bridge.translate_event(event)

        mock_tracer.start_span.assert_called_once()
        mock_counter.add.assert_called_once()
        mock_span.end.assert_called_once()
