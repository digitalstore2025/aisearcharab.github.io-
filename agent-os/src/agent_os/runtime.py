from __future__ import annotations

from dataclasses import dataclass, replace
from time import monotonic
from typing import Any, Callable, Protocol

from .reliability import (
    FailureSignal,
    RecoveryAction,
    RecoveryPolicy,
    RecoveryState,
)


class TraceSink(Protocol):
    def emit(self, event: str, **data: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """Safety metadata for one externally observable operation."""

    name: str
    idempotent: bool = False
    retry_after_verified_absence: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("operation name must not be empty")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    success: bool
    safe_stop: bool
    attempts: int
    tool_calls: int
    verification_calls: int
    actions: tuple[str, ...]
    recovered_by: str | None = None
    value: Any = None


class RecoveryExecutor:
    """Execute a tool operation under the deterministic RecoveryPolicy.

    The executor deliberately does not infer failure classes from exception text.
    Callers must provide a classifier that returns a structured FailureSignal.
    Raw exceptions, tool arguments, and return payloads are never emitted to the
    trace sink. Process-control exceptions such as KeyboardInterrupt/SystemExit
    are not swallowed by recovery.

    Elapsed-time enforcement is fail-closed before and after each operation call.
    A synchronous callable already in progress cannot be preempted safely here;
    transport/tool timeouts should therefore be configured no higher than the
    remaining recovery budget.
    """

    def __init__(self, policy: RecoveryPolicy | None = None, tracer: TraceSink | None = None):
        self.policy = policy or RecoveryPolicy()
        self.tracer = tracer

    def _emit(self, event: str, **data: Any) -> None:
        if self.tracer is not None:
            self.tracer.emit(event, **data)

    def _stopped(
        self,
        *,
        attempts: int,
        tool_calls: int,
        verification_calls: int,
        actions: list[str],
        recovered_by: str | None = None,
    ) -> ExecutionResult:
        self._emit(
            "recovery.execution.stopped",
            status="safe_stop",
            attempts=attempts,
            tool_calls=tool_calls,
            verification_calls=verification_calls,
            recovered_by=recovered_by,
        )
        return ExecutionResult(
            success=False,
            safe_stop=True,
            attempts=attempts,
            tool_calls=tool_calls,
            verification_calls=verification_calls,
            actions=tuple(actions),
            recovered_by=recovered_by,
        )

    def execute(
        self,
        spec: OperationSpec,
        operation: Callable[[], Any],
        classify: Callable[[Exception], FailureSignal],
        *,
        verify_postcondition: Callable[[], bool] | None = None,
        repair_arguments: Callable[[], None] | None = None,
        refresh_context: Callable[[], None] | None = None,
        replan: Callable[[], None] | None = None,
        human_gate_available: bool = True,
    ) -> ExecutionResult:
        start = monotonic()
        attempts = 0
        tool_calls = 0
        verification_calls = 0
        actions: list[str] = []

        while True:
            elapsed = monotonic() - start
            if (
                attempts >= self.policy.budget.max_attempts
                or tool_calls >= self.policy.budget.max_tool_calls
                or elapsed >= self.policy.budget.max_elapsed_seconds
            ):
                actions.append(RecoveryAction.ESCALATE.value if human_gate_available else RecoveryAction.ABSTAIN.value)
                return self._stopped(
                    attempts=attempts,
                    tool_calls=tool_calls,
                    verification_calls=verification_calls,
                    actions=actions,
                    recovered_by="budget_exhausted",
                )

            attempts += 1
            tool_calls += 1
            try:
                value = operation()
            except Exception as exc:
                signal = classify(exc)
                # A classifier may downgrade replay safety, but it must never be
                # able to elevate a non-idempotent operation into a blind retry.
                effective_signal = replace(
                    signal,
                    idempotent=bool(signal.idempotent and spec.idempotent),
                )
                state = RecoveryState(
                    attempts=attempts,
                    tool_calls=tool_calls,
                    elapsed_seconds=monotonic() - start,
                )
                decision = self.policy.decide(
                    effective_signal,
                    state,
                    human_gate_available=human_gate_available,
                )
                actions.append(decision.action.value)
                self._emit(
                    "recovery.decision",
                    tool=spec.name,
                    failure_class=signal.failure_class.value,
                    action=decision.action.value,
                    decision=decision.reason,
                    requires_verification=decision.requires_verification,
                    automatic=decision.automatic,
                    attempts=attempts,
                    tool_calls=tool_calls,
                    verification_calls=verification_calls,
                    remaining_attempts=decision.remaining_attempts,
                    remaining_tool_calls=decision.remaining_tool_calls,
                    duration_s=state.elapsed_seconds,
                    status="recovering",
                )

                if decision.action is RecoveryAction.RETRY:
                    continue

                if decision.action is RecoveryAction.VERIFY_BEFORE_RETRY:
                    if verify_postcondition is None:
                        return self._stopped(
                            attempts=attempts,
                            tool_calls=tool_calls,
                            verification_calls=verification_calls,
                            actions=actions,
                            recovered_by="verification_unavailable",
                        )
                    verification_calls += 1
                    try:
                        verified = bool(verify_postcondition())
                    except Exception:
                        return self._stopped(
                            attempts=attempts,
                            tool_calls=tool_calls,
                            verification_calls=verification_calls,
                            actions=actions,
                            recovered_by="verification_failed",
                        )
                    self._emit(
                        "recovery.postcondition",
                        tool=spec.name,
                        status="verified" if verified else "absent",
                        attempts=attempts,
                        tool_calls=tool_calls,
                        verification_calls=verification_calls,
                    )
                    if verified:
                        return ExecutionResult(
                            success=True,
                            safe_stop=False,
                            attempts=attempts,
                            tool_calls=tool_calls,
                            verification_calls=verification_calls,
                            actions=tuple(actions),
                            recovered_by="postcondition_verified",
                        )
                    if spec.idempotent or spec.retry_after_verified_absence:
                        continue
                    return self._stopped(
                        attempts=attempts,
                        tool_calls=tool_calls,
                        verification_calls=verification_calls,
                        actions=actions,
                        recovered_by="unsafe_replay_after_verified_absence",
                    )

                callback: Callable[[], None] | None = None
                if decision.action is RecoveryAction.REPAIR_ARGUMENTS:
                    callback = repair_arguments
                elif decision.action is RecoveryAction.REFRESH_CONTEXT:
                    callback = refresh_context
                elif decision.action is RecoveryAction.REPLAN:
                    callback = replan

                if callback is not None:
                    try:
                        callback()
                    except Exception:
                        return self._stopped(
                            attempts=attempts,
                            tool_calls=tool_calls,
                            verification_calls=verification_calls,
                            actions=actions,
                            recovered_by=f"{decision.action.value}_failed",
                        )
                    continue

                if decision.action in {
                    RecoveryAction.REPAIR_ARGUMENTS,
                    RecoveryAction.REFRESH_CONTEXT,
                    RecoveryAction.REPLAN,
                    RecoveryAction.ESCALATE,
                    RecoveryAction.ABSTAIN,
                }:
                    return self._stopped(
                        attempts=attempts,
                        tool_calls=tool_calls,
                        verification_calls=verification_calls,
                        actions=actions,
                        recovered_by=decision.action.value,
                    )

                return self._stopped(
                    attempts=attempts,
                    tool_calls=tool_calls,
                    verification_calls=verification_calls,
                    actions=actions,
                    recovered_by="unhandled_recovery_action",
                )

            elapsed_after_call = monotonic() - start
            if elapsed_after_call >= self.policy.budget.max_elapsed_seconds:
                actions.append(RecoveryAction.ESCALATE.value if human_gate_available else RecoveryAction.ABSTAIN.value)
                return self._stopped(
                    attempts=attempts,
                    tool_calls=tool_calls,
                    verification_calls=verification_calls,
                    actions=actions,
                    recovered_by="elapsed_budget_exhausted_after_call",
                )

            self._emit(
                "recovery.execution.completed",
                tool=spec.name,
                status="success",
                attempts=attempts,
                tool_calls=tool_calls,
                verification_calls=verification_calls,
                duration_s=elapsed_after_call,
            )
            return ExecutionResult(
                success=True,
                safe_stop=False,
                attempts=attempts,
                tool_calls=tool_calls,
                verification_calls=verification_calls,
                actions=tuple(actions),
                value=value,
            )
