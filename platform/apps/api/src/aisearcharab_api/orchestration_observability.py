from __future__ import annotations

import math
import re
from dataclasses import dataclass
from logging import Logger
from typing import Protocol, Sequence

from .orchestration import StepTrace

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")


class UnsafeTraceMetadata(ValueError):
    """Raised when trace metadata could inject logs or carry arbitrary payloads."""


def _safe_identifier(value: str | None, *, field: str, optional: bool = False) -> str | None:
    if value is None:
        if optional:
            return None
        raise UnsafeTraceMetadata(f"{field} is required")
    normalized = value.strip()
    if not normalized and optional:
        return None
    if not _SAFE_IDENTIFIER.fullmatch(normalized):
        raise UnsafeTraceMetadata(f"{field} contains unsupported characters or length")
    return normalized


@dataclass(frozen=True, slots=True)
class WorkflowTraceContext:
    workflow: str
    request_id: str | None = None

    def validated(self) -> WorkflowTraceContext:
        return WorkflowTraceContext(
            workflow=str(_safe_identifier(self.workflow, field="workflow")),
            request_id=_safe_identifier(self.request_id, field="request_id", optional=True),
        )


class TraceSink(Protocol):
    def emit(self, *, context: WorkflowTraceContext, trace: StepTrace) -> None: ...


class LoggingTraceSink:
    """Provider-neutral logging sink for payload-free workflow timing metadata.

    This sink intentionally accepts only a validated workflow identifier,
    optional request identifier, step identifier and duration. There is no field
    for query text, evidence, prompts, secrets, user IDs, tokens or model output.
    An OpenTelemetry adapter can implement the same TraceSink protocol later.
    """

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def emit(self, *, context: WorkflowTraceContext, trace: StepTrace) -> None:
        validated_context = context.validated()
        step = _safe_identifier(trace.name, field="step")
        duration_ms = float(trace.duration_ms)
        if not math.isfinite(duration_ms) or duration_ms < 0:
            raise UnsafeTraceMetadata("duration_ms must be finite and non-negative")
        self._logger.info(
            "workflow_step workflow=%s request_id=%s step=%s duration_ms=%.3f",
            validated_context.workflow,
            validated_context.request_id or "-",
            step,
            duration_ms,
        )


def emit_traces(
    sink: TraceSink,
    *,
    context: WorkflowTraceContext,
    traces: Sequence[StepTrace],
) -> None:
    validated_context = context.validated()
    for trace in traces:
        sink.emit(context=validated_context, trace=trace)
