from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FailureClass(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    MALFORMED_ARGUMENTS = "malformed_arguments"
    PARTIAL_STATE = "partial_state"
    STALE_CONTEXT = "stale_context"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    VERIFICATION_FAILED = "verification_failed"
    POLICY_DENIED = "policy_denied"
    UNKNOWN = "unknown"


class RecoveryAction(StrEnum):
    RETRY = "retry"
    VERIFY_BEFORE_RETRY = "verify_before_retry"
    REPAIR_ARGUMENTS = "repair_arguments"
    REFRESH_CONTEXT = "refresh_context"
    REPLAN = "replan"
    ESCALATE = "escalate"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class RecoveryBudget:
    """Finite recovery limits. Zero/negative values are rejected fail-closed."""

    max_attempts: int = 3
    max_tool_calls: int = 8
    max_elapsed_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if self.max_elapsed_seconds <= 0:
            raise ValueError("max_elapsed_seconds must be positive")


@dataclass(frozen=True, slots=True)
class RecoveryState:
    attempts: int = 0
    tool_calls: int = 0
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.attempts < 0 or self.tool_calls < 0 or self.elapsed_seconds < 0:
            raise ValueError("recovery state counters cannot be negative")


@dataclass(frozen=True, slots=True)
class FailureSignal:
    failure_class: FailureClass
    side_effect_uncertain: bool = False
    idempotent: bool = False
    has_alternative: bool = False
    postcondition_verified: bool | None = None


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str
    requires_verification: bool
    automatic: bool
    remaining_attempts: int
    remaining_tool_calls: int

    def trace_fields(self) -> dict[str, str | int | bool]:
        """Payload-minimized fields safe to attach to existing Agent OS traces."""
        return {
            "recovery_action": self.action.value,
            "recovery_reason": self.reason,
            "requires_verification": self.requires_verification,
            "automatic": self.automatic,
            "remaining_attempts": self.remaining_attempts,
            "remaining_tool_calls": self.remaining_tool_calls,
        }


class RecoveryPolicy:
    """Deterministic, bounded recovery policy for tool-augmented agent runtimes.

    The policy never blindly retries a call when the external side effect is
    uncertain. Policy denials are also never converted into an automatic retry.
    """

    def __init__(self, budget: RecoveryBudget | None = None):
        self.budget = budget or RecoveryBudget()

    def _remaining(self, state: RecoveryState) -> tuple[int, int]:
        return (
            max(0, self.budget.max_attempts - state.attempts),
            max(0, self.budget.max_tool_calls - state.tool_calls),
        )

    def _exhausted(self, state: RecoveryState) -> bool:
        return (
            state.attempts >= self.budget.max_attempts
            or state.tool_calls >= self.budget.max_tool_calls
            or state.elapsed_seconds >= self.budget.max_elapsed_seconds
        )

    def _decision(
        self,
        action: RecoveryAction,
        reason: str,
        state: RecoveryState,
        *,
        requires_verification: bool = False,
        automatic: bool = True,
    ) -> RecoveryDecision:
        attempts, tools = self._remaining(state)
        return RecoveryDecision(
            action=action,
            reason=reason,
            requires_verification=requires_verification,
            automatic=automatic,
            remaining_attempts=attempts,
            remaining_tool_calls=tools,
        )

    def decide(
        self,
        signal: FailureSignal,
        state: RecoveryState,
        *,
        human_gate_available: bool = True,
    ) -> RecoveryDecision:
        if self._exhausted(state):
            return self._decision(
                RecoveryAction.ESCALATE if human_gate_available else RecoveryAction.ABSTAIN,
                "recovery_budget_exhausted",
                state,
                automatic=False,
            )

        failure = signal.failure_class

        if failure is FailureClass.POLICY_DENIED:
            return self._decision(
                RecoveryAction.ESCALATE if human_gate_available else RecoveryAction.ABSTAIN,
                "policy_denial_is_not_retryable",
                state,
                automatic=False,
            )

        if signal.side_effect_uncertain or failure is FailureClass.PARTIAL_STATE:
            if signal.postcondition_verified is True:
                return self._decision(
                    RecoveryAction.REPLAN,
                    "side_effect_already_verified; continue_from_observed_state",
                    state,
                    requires_verification=False,
                )
            return self._decision(
                RecoveryAction.VERIFY_BEFORE_RETRY,
                "external_state_may_have_changed",
                state,
                requires_verification=True,
            )

        if failure in {
            FailureClass.TIMEOUT,
            FailureClass.RATE_LIMIT,
            FailureClass.UPSTREAM_UNAVAILABLE,
        }:
            if signal.idempotent:
                return self._decision(
                    RecoveryAction.RETRY,
                    "transient_failure_on_idempotent_operation",
                    state,
                    requires_verification=True,
                )
            if signal.has_alternative:
                return self._decision(
                    RecoveryAction.REPLAN,
                    "transient_failure_on_non_idempotent_path_with_alternative",
                    state,
                    requires_verification=True,
                )
            return self._decision(
                RecoveryAction.ESCALATE if human_gate_available else RecoveryAction.ABSTAIN,
                "transient_failure_but_safe_retry_not_proven",
                state,
                automatic=False,
            )

        if failure is FailureClass.MALFORMED_ARGUMENTS:
            return self._decision(
                RecoveryAction.REPAIR_ARGUMENTS,
                "repair_schema_or_arguments_before_another_call",
                state,
                requires_verification=True,
            )

        if failure is FailureClass.STALE_CONTEXT:
            return self._decision(
                RecoveryAction.REFRESH_CONTEXT,
                "refresh_stale_inputs_before_continuing",
                state,
                requires_verification=True,
            )

        if failure in {
            FailureClass.CONTRADICTORY_EVIDENCE,
            FailureClass.VERIFICATION_FAILED,
        }:
            if state.attempts + 1 >= self.budget.max_attempts:
                return self._decision(
                    RecoveryAction.ESCALATE if human_gate_available else RecoveryAction.ABSTAIN,
                    "verification_failed_near_budget_boundary",
                    state,
                    automatic=False,
                )
            return self._decision(
                RecoveryAction.REPLAN,
                "verification_or_evidence_conflict_requires_new_plan",
                state,
                requires_verification=True,
            )

        if state.attempts == 0:
            return self._decision(
                RecoveryAction.REPLAN,
                "unknown_failure_gets_one_bounded_replan",
                state,
                requires_verification=True,
            )

        return self._decision(
            RecoveryAction.ESCALATE if human_gate_available else RecoveryAction.ABSTAIN,
            "unknown_failure_not_safe_for_repeated_automatic_recovery",
            state,
            automatic=False,
        )


@dataclass(frozen=True, slots=True)
class ReliabilityOutcome:
    success: bool
    silent_failure: bool = False
    duplicate_action: bool = False
    attempts: int = 1
    tool_calls: int = 0

    def __post_init__(self) -> None:
        if self.attempts <= 0:
            raise ValueError("attempts must be positive")
        if self.tool_calls < 0:
            raise ValueError("tool_calls cannot be negative")


@dataclass(frozen=True, slots=True)
class ReliabilitySummary:
    runs: int
    success_rate: float
    silent_failure_rate: float
    duplicate_action_rate: float
    mean_attempts: float
    mean_tool_calls: float


def summarize_reliability(outcomes: list[ReliabilityOutcome]) -> ReliabilitySummary:
    if not outcomes:
        return ReliabilitySummary(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total = len(outcomes)
    return ReliabilitySummary(
        runs=total,
        success_rate=sum(o.success for o in outcomes) / total,
        silent_failure_rate=sum(o.silent_failure for o in outcomes) / total,
        duplicate_action_rate=sum(o.duplicate_action for o in outcomes) / total,
        mean_attempts=sum(o.attempts for o in outcomes) / total,
        mean_tool_calls=sum(o.tool_calls for o in outcomes) / total,
    )
