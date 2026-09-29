from __future__ import annotations

import time
import uuid
from typing import Any

from .tracing import sanitize_trace_data
from .types import TraceEvent


class OpenTelemetryTracer:
    """Optional OpenTelemetry trace sink using the same emit contract as JsonlTracer.

    OpenTelemetry is deliberately an optional dependency. The core Agent OS
    remains dependency-free; install the `otel` extra when this sink is used.
    Telemetry failures are isolated from control-plane execution: tracing may be
    lost, but recovery/tool execution must not fail because an exporter is down.
    """

    def __init__(self, tracer: Any | None = None, *, instrumentation_name: str = "astra-agent-os"):
        if tracer is None:
            try:
                from opentelemetry import trace
            except ImportError as exc:  # pragma: no cover - exercised in no-extra environments
                raise RuntimeError("OpenTelemetry support requires astra-agent-os[otel]") from exc
            tracer = trace.get_tracer(instrumentation_name)
        self._tracer = tracer
        self.trace_id = uuid.uuid4().hex

    @staticmethod
    def _attribute_value(value: Any) -> Any:
        if isinstance(value, list):
            return tuple(value)
        return value

    def emit(self, event: str, **data: Any) -> TraceEvent:
        safe = sanitize_trace_data(data)
        timestamp = time.time()
        try:
            with self._tracer.start_as_current_span(event) as span:
                span.set_attribute("agent_os.trace_id", self.trace_id)
                span.set_attribute("agent_os.event", event)
                for key, value in safe.items():
                    if value is None:
                        continue
                    try:
                        span.set_attribute(f"agent_os.{key}", self._attribute_value(value))
                    except (TypeError, ValueError):
                        span.set_attribute(f"agent_os.{key}", f"<{type(value).__name__}:redacted>")
        except Exception:
            # Observability is deliberately fail-isolated. Do not leak exporter
            # failures or allow them to abort recovery execution.
            pass
        return TraceEvent(self.trace_id, event, timestamp, safe)


class CompositeTracer:
    """Fan one payload-minimized event out to multiple trace sinks."""

    def __init__(self, *tracers: Any):
        if not tracers:
            raise ValueError("at least one tracer is required")
        self.tracers = tracers

    def emit(self, event: str, **data: Any) -> TraceEvent:
        first: TraceEvent | None = None
        for tracer in self.tracers:
            emitted = tracer.emit(event, **data)
            if first is None:
                first = emitted
        assert first is not None
        return first
