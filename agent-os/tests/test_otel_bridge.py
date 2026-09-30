import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.otel_bridge import CompositeTracer, OpenTelemetryTracer

try:
    import opentelemetry.sdk  # noqa: F401
except ImportError:
    HAS_OTEL_SDK = False
else:
    HAS_OTEL_SDK = True


class _FakeTracer:
    def __init__(self):
        self.events = []

    def emit(self, event, **data):
        self.events.append((event, data))
        return type("Event", (), {"event": event})()


class _BrokenOtelTracer:
    def start_as_current_span(self, event):
        raise RuntimeError("exporter unavailable")


class TestCompositeTracer(unittest.TestCase):
    def test_fans_out_to_all_sinks(self):
        a = _FakeTracer()
        b = _FakeTracer()
        composite = CompositeTracer(a, b)
        composite.emit("recovery.test", tool="read", status="ok")
        self.assertEqual(len(a.events), 1)
        self.assertEqual(len(b.events), 1)

    def test_requires_at_least_one_sink(self):
        with self.assertRaises(ValueError):
            CompositeTracer()

    def test_otel_failure_is_isolated_from_control_plane(self):
        sink = OpenTelemetryTracer(_BrokenOtelTracer())
        event = sink.emit(
            "recovery.decision",
            tool="safe-tool",
            status="recovering",
            credential="SHOULD-NOT-APPEAR",
        )
        self.assertEqual(event.event, "recovery.decision")
        self.assertNotIn("credential", event.data)
        self.assertEqual(event.data["redacted_fields"], ["credential"])


@unittest.skipUnless(HAS_OTEL_SDK, "OpenTelemetry SDK extra not installed")
class TestOpenTelemetryIntegration(unittest.TestCase):
    def test_emits_sanitized_span_attributes(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("agent-os-test")
        sink = OpenTelemetryTracer(tracer)

        sink.emit(
            "recovery.decision",
            tool="safe-tool",
            action="retry",
            status="recovering",
            credential="SHOULD-NOT-APPEAR",
        )

        spans = exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        attrs = spans[0].attributes
        self.assertEqual(attrs["agent_os.tool"], "safe-tool")
        self.assertEqual(attrs["agent_os.action"], "retry")
        self.assertEqual(tuple(attrs["agent_os.redacted_fields"]), ("credential",))
        self.assertNotIn("SHOULD-NOT-APPEAR", repr(attrs))


if __name__ == "__main__":
    unittest.main()
