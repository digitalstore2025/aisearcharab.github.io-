from __future__ import annotations

import pytest

from aisearcharab_api.orchestration import (
    DuplicateRegistrationError,
    Evaluation,
    UnknownRouteError,
    UnknownWorkerError,
    run_evaluator_loop,
    run_orchestrator_workers,
    run_parallel,
    run_routed,
    run_sequential,
)


def test_sequential_runs_in_order_without_payload_traces() -> None:
    result = run_sequential(
        2,
        (
            ("double", lambda value: int(value) * 2),
            ("increment", lambda value: int(value) + 1),
        ),
    )

    assert result.value == 5
    assert [trace.name for trace in result.traces] == ["double", "increment"]
    assert all(trace.duration_ms >= 0 for trace in result.traces)


def test_parallel_preserves_registration_order() -> None:
    result = run_parallel(
        "arabic",
        {
            "length": len,
            "upper": str.upper,
        },
        max_workers=2,
    )

    assert list(result.outputs) == ["length", "upper"]
    assert result.outputs == {"length": 6, "upper": "ARABIC"}
    assert [trace.name for trace in result.traces] == ["length", "upper"]


def test_routing_dispatches_only_registered_handler() -> None:
    result = run_routed(
        "grounded",
        lambda value: value,
        {
            "search": lambda _value: "search-result",
            "grounded": lambda _value: "grounded-result",
        },
    )

    assert result.route == "grounded"
    assert result.value == "grounded-result"
    assert result.trace.name == "route:grounded"


def test_routing_rejects_unknown_route() -> None:
    with pytest.raises(UnknownRouteError):
        run_routed("external", lambda value: value, {"search": lambda _value: "ok"})


def test_orchestrator_deduplicates_plan_and_aggregates() -> None:
    result = run_orchestrator_workers(
        3,
        planner=lambda _value: ("square", "double", "square"),
        workers={
            "square": lambda value: value * value,
            "double": lambda value: value * 2,
        },
        aggregator=lambda outputs: sum(outputs.values()),
        max_workers=2,
    )

    assert result.plan == ("square", "double")
    assert result.worker_outputs == {"square": 9, "double": 6}
    assert result.value == 15
    assert [trace.name for trace in result.traces] == ["square", "double", "aggregate"]


def test_orchestrator_rejects_unknown_worker() -> None:
    with pytest.raises(UnknownWorkerError):
        run_orchestrator_workers(
            "query",
            planner=lambda _value: ("missing",),
            workers={},
            aggregator=lambda outputs: outputs,
        )


def test_evaluator_loop_refines_until_accepted() -> None:
    result = run_evaluator_loop(
        1,
        generator=lambda seed: seed,
        evaluator=lambda candidate: Evaluation(
            accepted=candidate >= 3,
            feedback="increase",
        ),
        refiner=lambda candidate, _evaluation: candidate + 1,
        max_iterations=4,
    )

    assert result.value == 3
    assert result.accepted is True
    assert [iteration.accepted for iteration in result.iterations] == [False, False, True]


def test_evaluator_loop_stops_at_hard_limit() -> None:
    result = run_evaluator_loop(
        "draft",
        generator=lambda seed: seed,
        evaluator=lambda _candidate: Evaluation(accepted=False, feedback="still weak"),
        refiner=lambda candidate, _evaluation: candidate + "!",
        max_iterations=2,
    )

    assert result.value == "draft!"
    assert result.accepted is False
    assert len(result.iterations) == 2


@pytest.mark.parametrize("value", [0, 11])
def test_evaluator_loop_enforces_iteration_bounds(value: int) -> None:
    with pytest.raises(ValueError):
        run_evaluator_loop(
            "draft",
            generator=lambda seed: seed,
            evaluator=lambda _candidate: Evaluation(accepted=True),
            refiner=lambda candidate, _evaluation: candidate,
            max_iterations=value,
        )


def test_parallel_rejects_colliding_normalized_worker_names() -> None:
    with pytest.raises(DuplicateRegistrationError):
        run_parallel(
            "query",
            {
                "worker": lambda value: value,
                " worker ": lambda value: value,
            },
        )


def test_routing_rejects_colliding_normalized_route_names() -> None:
    with pytest.raises(DuplicateRegistrationError):
        run_routed(
            "search",
            lambda value: value,
            {
                "search": lambda _value: "a",
                " search ": lambda _value: "b",
            },
        )
