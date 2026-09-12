from __future__ import annotations

import logging

import pytest

from aisearcharab_api.orchestration import StepTrace
from aisearcharab_api.orchestration_observability import (
    LoggingTraceSink,
    UnsafeTraceMetadata,
    WorkflowTraceContext,
    emit_traces,
)


def test_logging_sink_emits_only_identifiers_and_duration(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("aisearcharab.tests.workflow")
    sink = LoggingTraceSink(logger)

    with caplog.at_level(logging.INFO, logger=logger.name):
        emit_traces(
            sink,
            context=WorkflowTraceContext(
                workflow="grounded_answer",
                request_id="123e4567-e89b-12d3-a456-426614174000",
            ),
            traces=(StepTrace(name="retrieve_evidence", duration_ms=4.25),),
        )

    rendered = caplog.text
    assert "workflow=grounded_answer" in rendered
    assert "step=retrieve_evidence" in rendered
    assert "duration_ms=4.250" in rendered
    assert "123e4567-e89b-12d3-a456-426614174000" in rendered
    assert "query=" not in rendered
    assert "evidence=" not in rendered
    assert "prompt=" not in rendered


@pytest.mark.parametrize(
    ("context", "trace"),
    [
        (WorkflowTraceContext(workflow="grounded\nsecret"), StepTrace(name="step", duration_ms=1.0)),
        (WorkflowTraceContext(workflow="grounded"), StepTrace(name="step\nsecret", duration_ms=1.0)),
        (WorkflowTraceContext(workflow="grounded", request_id="id\rsecret"), StepTrace(name="step", duration_ms=1.0)),
    ],
)
def test_logging_sink_rejects_log_injection_metadata(
    context: WorkflowTraceContext,
    trace: StepTrace,
) -> None:
    with pytest.raises(UnsafeTraceMetadata):
        LoggingTraceSink(logging.getLogger("aisearcharab.tests.workflow")).emit(
            context=context,
            trace=trace,
        )


@pytest.mark.parametrize("duration", [-1.0, float("nan"), float("inf")])
def test_logging_sink_rejects_invalid_durations(duration: float) -> None:
    with pytest.raises(UnsafeTraceMetadata):
        LoggingTraceSink(logging.getLogger("aisearcharab.tests.workflow")).emit(
            context=WorkflowTraceContext(workflow="grounded_answer"),
            trace=StepTrace(name="step", duration_ms=duration),
        )
