"""Optional live-eval adapter.

This file intentionally keeps provider calls outside the core package. Supply a callable
that accepts a task string and returns a structured result. Store no secrets in eval cases.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Any


@dataclass
class LiveMetrics:
    success: bool
    latency_s: float
    tool_calls: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    notes: str = ""


def evaluate(task: str, runner: Callable[[str], dict[str, Any]], judge: Callable[[dict[str, Any]], tuple[bool, str]]) -> LiveMetrics:
    start = time.perf_counter()
    result = runner(task)
    latency = time.perf_counter() - start
    ok, notes = judge(result)
    usage = result.get("usage", {})
    return LiveMetrics(
        success=ok,
        latency_s=latency,
        tool_calls=len(result.get("tool_calls", [])),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        cost_usd=result.get("cost_usd"),
        notes=notes,
    )
