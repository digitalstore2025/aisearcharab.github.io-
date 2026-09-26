from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from math import sqrt
import random
from typing import Iterable

from .reliability import (
    FailureClass,
    FailureSignal,
    RecoveryAction,
    RecoveryBudget,
    RecoveryPolicy,
    RecoveryState,
    ReliabilityOutcome,
    summarize_reliability,
)


BENCHMARK_VERSION = "1.0.0"
DEFAULT_SEED = 20260926


class Strategy(StrEnum):
    NO_RECOVERY = "no_recovery"
    RETRY_ONLY = "retry_only"
    BOUNDED = "bounded_recovery"
    BOUNDED_VERIFIED = "bounded_recovery_with_verifier"


@dataclass(frozen=True, slots=True)
class FaultScenario:
    id: str
    failure_class: FailureClass
    description: str
    idempotent: bool = False
    side_effect_uncertain: bool = False
    has_alternative: bool = False
    policy_denial: bool = False
    verifier_required: bool = False
    retry_can_succeed: bool = False
    repair_can_succeed: bool = False
    refresh_can_succeed: bool = False
    replan_can_succeed: bool = False
    first_call_mutates: bool = False
    repeat_mutation_is_duplicate: bool = False
    baseline_silent_failure: bool = False


SCENARIOS: tuple[FaultScenario, ...] = (
    FaultScenario(
        "timeout_after_dispatch",
        FailureClass.TIMEOUT,
        "Tool commits an external mutation but the response times out.",
        side_effect_uncertain=True,
        verifier_required=True,
        first_call_mutates=True,
        repeat_mutation_is_duplicate=True,
    ),
    FaultScenario(
        "rate_limit",
        FailureClass.RATE_LIMIT,
        "First call returns HTTP 429; a later bounded retry can succeed.",
        idempotent=True,
        retry_can_succeed=True,
    ),
    FaultScenario(
        "partial_state",
        FailureClass.PARTIAL_STATE,
        "External state is partially committed and the result is ambiguous.",
        side_effect_uncertain=True,
        verifier_required=True,
        first_call_mutates=True,
        repeat_mutation_is_duplicate=True,
    ),
    FaultScenario(
        "malformed_arguments",
        FailureClass.MALFORMED_ARGUMENTS,
        "Tool rejects malformed arguments before executing.",
        repair_can_succeed=True,
    ),
    FaultScenario(
        "stale_evidence",
        FailureClass.STALE_CONTEXT,
        "The current evidence snapshot is stale.",
        refresh_can_succeed=True,
        baseline_silent_failure=True,
    ),
    FaultScenario(
        "contradictory_evidence",
        FailureClass.CONTRADICTORY_EVIDENCE,
        "Two evidence paths conflict and require a new verified plan.",
        replan_can_succeed=True,
        baseline_silent_failure=True,
    ),
    FaultScenario(
        "delayed_visibility",
        FailureClass.PARTIAL_STATE,
        "Mutation succeeds but read-after-write visibility is delayed.",
        side_effect_uncertain=True,
        verifier_required=True,
        first_call_mutates=True,
        repeat_mutation_is_duplicate=True,
    ),
    FaultScenario(
        "policy_denial",
        FailureClass.POLICY_DENIED,
        "Requested operation is denied by policy and must not be retried.",
        policy_denial=True,
    ),
    FaultScenario(
        "irreversible_side_effect_ambiguity",
        FailureClass.TIMEOUT,
        "An irreversible operation may have completed before the connection failed.",
        side_effect_uncertain=True,
        verifier_required=True,
        first_call_mutates=True,
        repeat_mutation_is_duplicate=True,
    ),
)


@dataclass(frozen=True, slots=True)
class CaseResult:
    scenario: str
    strategy: str
    success: bool
    silent_failure: bool
    duplicate_action: bool
    safe_stop: bool
    attempts: int
    tool_calls: int
    final_action: str

    def outcome(self) -> ReliabilityOutcome:
        return ReliabilityOutcome(
            success=self.success,
            silent_failure=self.silent_failure,
            duplicate_action=self.duplicate_action,
            attempts=self.attempts,
            tool_calls=self.tool_calls,
        )


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    margin = z * sqrt((p * (1 - p) / total) + (z2 / (4 * total * total))) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def _transient_retry_succeeds(scenario: FaultScenario, rng: random.Random) -> bool:
    if not scenario.retry_can_succeed:
        return False
    # Stable stochastic surface: most transient retries recover, but not all.
    return rng.random() < 0.8


def simulate_case(
    scenario: FaultScenario,
    strategy: Strategy,
    *,
    seed: int,
    budget: RecoveryBudget | None = None,
) -> CaseResult:
    rng = random.Random(seed)
    budget = budget or RecoveryBudget(max_attempts=3, max_tool_calls=5, max_elapsed_seconds=30)
    policy = RecoveryPolicy(budget)

    attempts = 1
    tool_calls = 1
    mutation_count = 1 if scenario.first_call_mutates else 0
    safe_stop = False
    silent_failure = False
    success = False
    final_action = "initial_failure"

    if scenario.policy_denial:
        if strategy is Strategy.RETRY_ONLY:
            attempts += 1
            tool_calls += 1
            final_action = "unsafe_policy_retry"
            return CaseResult(scenario.id, strategy.value, False, False, False, False, attempts, tool_calls, final_action)
        final_action = "policy_safe_stop"
        return CaseResult(scenario.id, strategy.value, True, False, False, True, attempts, tool_calls, final_action)

    if strategy is Strategy.NO_RECOVERY:
        if scenario.baseline_silent_failure:
            silent_failure = True
            final_action = "accepted_unverified_output"
        else:
            final_action = "stopped_after_failure"
        return CaseResult(scenario.id, strategy.value, False, silent_failure, False, True, attempts, tool_calls, final_action)

    if strategy is Strategy.RETRY_ONLY:
        attempts += 1
        tool_calls += 1
        if scenario.first_call_mutates:
            mutation_count += 1
        duplicate = scenario.repeat_mutation_is_duplicate and mutation_count > 1
        if scenario.baseline_silent_failure:
            silent_failure = True
            final_action = "repeated_same_bad_path"
            return CaseResult(scenario.id, strategy.value, False, True, duplicate, False, attempts, tool_calls, final_action)
        if _transient_retry_succeeds(scenario, rng):
            final_action = "retry_succeeded"
            return CaseResult(scenario.id, strategy.value, not duplicate, False, duplicate, False, attempts, tool_calls, final_action)
        final_action = "retry_failed"
        return CaseResult(scenario.id, strategy.value, False, False, duplicate, False, attempts, tool_calls, final_action)

    state = RecoveryState(attempts=1, tool_calls=1, elapsed_seconds=1.0)
    signal = FailureSignal(
        scenario.failure_class,
        side_effect_uncertain=scenario.side_effect_uncertain,
        idempotent=scenario.idempotent,
        has_alternative=scenario.has_alternative,
    )
    decision = policy.decide(signal, state, human_gate_available=True)
    final_action = decision.action.value

    if decision.action is RecoveryAction.RETRY:
        attempts += 1
        tool_calls += 1
        if _transient_retry_succeeds(scenario, rng):
            success = True
        return CaseResult(scenario.id, strategy.value, success, False, False, not success, attempts, tool_calls, final_action)

    if decision.action is RecoveryAction.REPAIR_ARGUMENTS:
        attempts += 1
        tool_calls += 1
        success = scenario.repair_can_succeed
        return CaseResult(scenario.id, strategy.value, success, False, False, not success, attempts, tool_calls, final_action)

    if decision.action is RecoveryAction.REFRESH_CONTEXT:
        attempts += 1
        success = scenario.refresh_can_succeed
        return CaseResult(scenario.id, strategy.value, success, False, False, not success, attempts, tool_calls, final_action)

    if decision.action is RecoveryAction.REPLAN:
        attempts += 1
        success = scenario.replan_can_succeed
        return CaseResult(scenario.id, strategy.value, success, False, False, not success, attempts, tool_calls, final_action)

    if decision.action is RecoveryAction.VERIFY_BEFORE_RETRY:
        if strategy is Strategy.BOUNDED:
            # A policy can demand verification, but without a verifier it must stop safely.
            return CaseResult(scenario.id, strategy.value, False, False, False, True, attempts, tool_calls, "verification_unavailable_safe_stop")

        # Independent verifier checks state before any replay. This costs an observation,
        # not another side-effecting tool execution.
        attempts += 1
        if scenario.verifier_required and scenario.first_call_mutates:
            success = True
            return CaseResult(scenario.id, strategy.value, True, False, False, False, attempts, tool_calls, "postcondition_verified")
        return CaseResult(scenario.id, strategy.value, False, False, False, True, attempts, tool_calls, "postcondition_not_verified")

    if decision.action in {RecoveryAction.ESCALATE, RecoveryAction.ABSTAIN}:
        safe_stop = True
        return CaseResult(scenario.id, strategy.value, False, False, False, safe_stop, attempts, tool_calls, final_action)

    return CaseResult(scenario.id, strategy.value, False, False, False, True, attempts, tool_calls, final_action)


def run_benchmark(
    *,
    repeats: int = 20,
    seed: int = DEFAULT_SEED,
    scenarios: Iterable[FaultScenario] = SCENARIOS,
) -> dict:
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    scenarios = tuple(scenarios)
    if not scenarios:
        raise ValueError("at least one scenario is required")

    strategies = tuple(Strategy)
    results: list[CaseResult] = []
    for scenario_index, scenario in enumerate(scenarios):
        for repeat in range(repeats):
            case_seed = seed + scenario_index * 10_000 + repeat
            for strategy in strategies:
                results.append(simulate_case(scenario, strategy, seed=case_seed))

    aggregate: dict[str, dict] = {}
    for strategy in strategies:
        selected = [r for r in results if r.strategy == strategy.value]
        summary = summarize_reliability([r.outcome() for r in selected])
        successes = sum(r.success for r in selected)
        silent = sum(r.silent_failure for r in selected)
        duplicates = sum(r.duplicate_action for r in selected)
        safe_stops = sum(r.safe_stop for r in selected)
        aggregate[strategy.value] = {
            **asdict(summary),
            "success_ci95": wilson_interval(successes, len(selected)),
            "silent_failure_ci95": wilson_interval(silent, len(selected)),
            "duplicate_action_ci95": wilson_interval(duplicates, len(selected)),
            "safe_stop_rate": safe_stops / len(selected),
        }

    by_scenario: dict[str, dict[str, dict]] = {}
    for scenario in scenarios:
        by_scenario[scenario.id] = {}
        for strategy in strategies:
            selected = [r for r in results if r.scenario == scenario.id and r.strategy == strategy.value]
            by_scenario[scenario.id][strategy.value] = {
                "runs": len(selected),
                "success_rate": sum(r.success for r in selected) / len(selected),
                "silent_failure_rate": sum(r.silent_failure for r in selected) / len(selected),
                "duplicate_action_rate": sum(r.duplicate_action for r in selected) / len(selected),
                "safe_stop_rate": sum(r.safe_stop for r in selected) / len(selected),
                "actions": sorted({r.final_action for r in selected}),
            }

    return {
        "benchmark_version": BENCHMARK_VERSION,
        "seed": seed,
        "repeats_per_scenario": repeats,
        "scenario_count": len(scenarios),
        "strategies": [s.value for s in strategies],
        "limitations": [
            "Synthetic deterministic policy benchmark; not a live model or production tool benchmark.",
            "Injected faults model control semantics and do not estimate real provider failure frequencies.",
            "Production promotion requires live postcondition probes, staging evidence, and human/security governance.",
        ],
        "aggregate": aggregate,
        "by_scenario": by_scenario,
    }
