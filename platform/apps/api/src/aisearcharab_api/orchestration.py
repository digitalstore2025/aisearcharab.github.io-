from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")
AggregateT = TypeVar("AggregateT")


class OrchestrationError(RuntimeError):
    """Base exception for local orchestration failures."""


class UnknownRouteError(OrchestrationError):
    """Raised when routing selects a handler that is not registered."""


class UnknownWorkerError(OrchestrationError):
    """Raised when an orchestrator selects a worker that is not registered."""


@dataclass(frozen=True, slots=True)
class StepTrace:
    name: str
    duration_ms: float


@dataclass(frozen=True, slots=True)
class PipelineResult(Generic[OutputT]):
    value: OutputT
    traces: tuple[StepTrace, ...]


@dataclass(frozen=True, slots=True)
class ParallelResult(Generic[OutputT]):
    outputs: dict[str, OutputT]
    traces: tuple[StepTrace, ...]


@dataclass(frozen=True, slots=True)
class RoutedResult(Generic[OutputT]):
    route: str
    value: OutputT
    trace: StepTrace


@dataclass(frozen=True, slots=True)
class OrchestratedResult(Generic[OutputT, AggregateT]):
    plan: tuple[str, ...]
    worker_outputs: dict[str, OutputT]
    value: AggregateT
    traces: tuple[StepTrace, ...]


@dataclass(frozen=True, slots=True)
class Evaluation:
    accepted: bool
    feedback: str = ""


@dataclass(frozen=True, slots=True)
class EvaluationIteration:
    iteration: int
    accepted: bool
    duration_ms: float


@dataclass(frozen=True, slots=True)
class EvaluationLoopResult(Generic[OutputT]):
    value: OutputT
    accepted: bool
    evaluation: Evaluation
    iterations: tuple[EvaluationIteration, ...]


def _validate_name(name: str, *, kind: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError(f"{kind} name must not be empty")
    if len(normalized) > 128:
        raise ValueError(f"{kind} name must be at most 128 characters")
    return normalized


def _timed_call(name: str, function: Callable[[], OutputT]) -> tuple[OutputT, StepTrace]:
    started = perf_counter()
    value = function()
    duration_ms = (perf_counter() - started) * 1000
    return value, StepTrace(name=name, duration_ms=round(duration_ms, 3))


def run_sequential(
    initial: object,
    steps: Sequence[tuple[str, Callable[[object], object]]],
) -> PipelineResult[object]:
    """Run deterministic local steps in order.

    Traces contain only step identifiers and durations. Payloads are intentionally
    excluded so callers do not accidentally copy query text, secrets, or evidence
    into routine orchestration telemetry.
    """
    value = initial
    traces: list[StepTrace] = []
    for raw_name, step in steps:
        name = _validate_name(raw_name, kind="step")
        value, trace = _timed_call(name, lambda step=step, value=value: step(value))
        traces.append(trace)
    return PipelineResult(value=value, traces=tuple(traces))


def run_parallel(
    input_value: InputT,
    workers: Mapping[str, Callable[[InputT], OutputT]],
    *,
    max_workers: int = 4,
) -> ParallelResult[OutputT]:
    """Run independent synchronous workers concurrently.

    The returned dictionary preserves registration order, not completion order.
    Workers that access SQLAlchemy must create/use independent sessions because a
    Session must not be shared across threads.
    """
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    ordered_workers = [(_validate_name(name, kind="worker"), worker) for name, worker in workers.items()]
    if not ordered_workers:
        return ParallelResult(outputs={}, traces=())

    def invoke(name: str, worker: Callable[[InputT], OutputT]) -> tuple[str, OutputT, StepTrace]:
        output, trace = _timed_call(name, lambda: worker(input_value))
        return name, output, trace

    completed: dict[str, tuple[OutputT, StepTrace]] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(ordered_workers))) as executor:
        futures = [executor.submit(invoke, name, worker) for name, worker in ordered_workers]
        for future in futures:
            name, output, trace = future.result()
            completed[name] = (output, trace)

    outputs = {name: completed[name][0] for name, _worker in ordered_workers}
    traces = tuple(completed[name][1] for name, _worker in ordered_workers)
    return ParallelResult(outputs=outputs, traces=traces)


def run_routed(
    input_value: InputT,
    route_selector: Callable[[InputT], str],
    handlers: Mapping[str, Callable[[InputT], OutputT]],
) -> RoutedResult[OutputT]:
    """Select exactly one registered handler using a local routing function."""
    route = _validate_name(route_selector(input_value), kind="route")
    handler = handlers.get(route)
    if handler is None:
        raise UnknownRouteError(f"unregistered route: {route}")
    value, trace = _timed_call(f"route:{route}", lambda: handler(input_value))
    return RoutedResult(route=route, value=value, trace=trace)


def run_orchestrator_workers(
    input_value: InputT,
    planner: Callable[[InputT], Sequence[str]],
    workers: Mapping[str, Callable[[InputT], OutputT]],
    aggregator: Callable[[Mapping[str, OutputT]], AggregateT],
    *,
    max_workers: int = 4,
) -> OrchestratedResult[OutputT, AggregateT]:
    """Plan a bounded worker set, run it, then aggregate the outputs."""
    plan = tuple(dict.fromkeys(_validate_name(name, kind="worker") for name in planner(input_value)))
    unknown = [name for name in plan if name not in workers]
    if unknown:
        raise UnknownWorkerError(f"unregistered workers: {', '.join(unknown)}")

    selected = {name: workers[name] for name in plan}
    parallel = run_parallel(input_value, selected, max_workers=max_workers)
    aggregate, aggregate_trace = _timed_call("aggregate", lambda: aggregator(parallel.outputs))
    return OrchestratedResult(
        plan=plan,
        worker_outputs=parallel.outputs,
        value=aggregate,
        traces=(*parallel.traces, aggregate_trace),
    )


def run_evaluator_loop(
    seed: InputT,
    generator: Callable[[InputT], OutputT],
    evaluator: Callable[[OutputT], Evaluation],
    refiner: Callable[[OutputT, Evaluation], OutputT],
    *,
    max_iterations: int = 3,
) -> EvaluationLoopResult[OutputT]:
    """Generate, evaluate, and refine with a hard iteration ceiling.

    `max_iterations` counts evaluations. The function always terminates and
    returns the last candidate even when it is not accepted.
    """
    if max_iterations < 1 or max_iterations > 10:
        raise ValueError("max_iterations must be between 1 and 10")

    candidate = generator(seed)
    iterations: list[EvaluationIteration] = []
    evaluation = Evaluation(accepted=False, feedback="")

    for iteration in range(1, max_iterations + 1):
        started = perf_counter()
        evaluation = evaluator(candidate)
        duration_ms = (perf_counter() - started) * 1000
        iterations.append(
            EvaluationIteration(
                iteration=iteration,
                accepted=evaluation.accepted,
                duration_ms=round(duration_ms, 3),
            )
        )
        if evaluation.accepted:
            return EvaluationLoopResult(
                value=candidate,
                accepted=True,
                evaluation=evaluation,
                iterations=tuple(iterations),
            )
        if iteration < max_iterations:
            candidate = refiner(candidate, evaluation)

    return EvaluationLoopResult(
        value=candidate,
        accepted=False,
        evaluation=evaluation,
        iterations=tuple(iterations),
    )
