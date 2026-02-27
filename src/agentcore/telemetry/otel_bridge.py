"""OpenTelemetry bridge for agentcore-sdk.

Translates ``AgentEvent`` objects into OTel spans and metrics.  The bridge
gracefully degrades to a no-op implementation when the ``opentelemetry-api``
package is not installed, so the rest of the SDK does not need OTel as a
hard dependency.

Shipped in this module
----------------------
- OTelBridge   — translates AgentEvents into OTel spans and metrics.
                 Falls back to no-op when ``opentelemetry-api`` is absent.

Extension points
-------------------
OTLP gRPC / HTTP exporters, baggage propagation, exemplar attachment, and
span linking across distributed agent hops are available via plugins.
"""
from __future__ import annotations

import logging

from agentcore.schema.events import AgentEvent

logger = logging.getLogger(__name__)

# Attempt to import the OpenTelemetry API.  Everything is optional.
try:
    from opentelemetry import metrics as otel_metrics  # type: ignore[import-not-found]
    from opentelemetry import trace as otel_trace  # type: ignore[import-not-found]
    from opentelemetry.trace import Span  # type: ignore[import-not-found]

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    otel_trace = None  # type: ignore[assignment]
    otel_metrics = None  # type: ignore[assignment]


class OTelBridge:
    """Translates ``AgentEvent`` objects into OpenTelemetry spans and metrics.

    When the ``opentelemetry-api`` package is installed, events are forwarded
    to the configured OTel SDK.  When it is absent, all calls are silently
    discarded — the bridge never raises due to a missing dependency.

    Parameters
    ----------
    service_name:
        The OTel ``service.name`` resource attribute.  Defaults to
        ``"agentcore"``.
    tracer_name:
        The tracer name registered with the OTel SDK.  Defaults to
        ``"agentcore.otel_bridge"``.

    Examples
    --------
    >>> bridge = OTelBridge()
    >>> bridge.is_available()
    False  # unless opentelemetry-api is installed
    """

    def __init__(
        self,
        service_name: str = "agentcore",
        tracer_name: str = "agentcore.otel_bridge",
    ) -> None:
        self._service_name = service_name
        self._tracer_name = tracer_name
        self._active_spans: dict[str, object] = {}

        if _OTEL_AVAILABLE:
            self._tracer = otel_trace.get_tracer(tracer_name)
            self._meter = otel_metrics.get_meter(tracer_name)
            self._event_counter = self._meter.create_counter(
                name="agentcore.events.total",
                description="Total number of agent events emitted.",
            )
        else:
            self._tracer = None
            self._meter = None
            self._event_counter = None
            logger.debug(
                "opentelemetry-api not installed; OTelBridge running in no-op mode."
            )

    def is_available(self) -> bool:
        """Return ``True`` if ``opentelemetry-api`` is installed.

        Returns
        -------
        bool
        """
        return _OTEL_AVAILABLE

    def start_span(self, event: AgentEvent) -> str | None:
        """Start an OTel span for *event* and return an opaque span key.

        If OTel is not available, returns ``None`` immediately.

        Parameters
        ----------
        event:
            The event to represent as a span.

        Returns
        -------
        str | None
            The span key to pass to :meth:`end_span`, or ``None``.
        """
        if not _OTEL_AVAILABLE or self._tracer is None:
            return None
        span_name = f"agentcore.{event.event_type.value}"
        span = self._tracer.start_span(
            span_name,
            attributes={
                "agent.id": event.agent_id,
                "event.id": event.event_id,
                "event.type": event.event_type.value,
            },
        )
        span_key = event.event_id
        self._active_spans[span_key] = span
        return span_key

    def end_span(self, span_key: str | None) -> None:
        """End the span associated with *span_key*.

        Parameters
        ----------
        span_key:
            The value returned by :meth:`start_span`.
        """
        if not _OTEL_AVAILABLE or span_key is None:
            return
        span = self._active_spans.pop(span_key, None)
        if span is not None:
            span.end()  # type: ignore[union-attr]

    def record_event(self, event: AgentEvent) -> None:
        """Increment the event counter metric for *event*.

        Parameters
        ----------
        event:
            The event to count.
        """
        if not _OTEL_AVAILABLE or self._event_counter is None:
            return
        self._event_counter.add(
            1,
            attributes={
                "event.type": event.event_type.value,
                "agent.id": event.agent_id,
            },
        )

    def record_metric(
        self,
        name: str,
        value: float,
        attributes: dict[str, str] | None = None,
    ) -> None:
        """Record an arbitrary float metric via the OTel meter.

        Parameters
        ----------
        name:
            OTel metric name.
        value:
            Numeric value to record.
        attributes:
            OTel attribute dict.
        """
        if not _OTEL_AVAILABLE or self._meter is None:
            return
        histogram = self._meter.create_histogram(
            name=name,
            description=f"agentcore metric: {name}",
        )
        histogram.record(value, attributes=attributes or {})

    def flush(self) -> None:
        """Flush any pending OTel data via the SDK's force-flush mechanism.

        This is a best-effort call; if OTel is not installed or the provider
        does not support force-flush, this method returns silently.
        """
        if not _OTEL_AVAILABLE:
            return
        try:
            provider = otel_trace.get_tracer_provider()  # type: ignore[union-attr]
            if hasattr(provider, "force_flush"):
                provider.force_flush()
        except Exception:  # noqa: BLE001
            logger.debug("OTelBridge.flush() encountered an error; ignoring.")

    def translate_event(self, event: AgentEvent) -> None:
        """Convenience method: start a span, record the event counter, end.

        Suitable for one-shot translation when you do not need to track the
        span across async boundaries.

        Parameters
        ----------
        event:
            The event to translate.
        """
        span_key = self.start_span(event)
        self.record_event(event)
        self.end_span(span_key)
