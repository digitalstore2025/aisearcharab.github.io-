# Late-completion corrective review

Date: 2026-09-30
Base: `8dadfcc67a93acf4091fc3890b5cb4775e383df5`
Source finding: post-merge review of PR #137

## Defect

PR #137 correctly prevented classifier-driven blind retries for non-idempotent operations, but its post-call elapsed-budget branch reclassified an already successful synchronous operation as `success=False`, discarded its returned value, and emitted a stopped execution.

For mutating non-idempotent calls this can contradict externally committed state and can induce a duplicate action if an upstream caller retries the reported failure.

## Correct semantics

- Budget exhausted before dispatch: do not invoke the operation; external outcome is `not_applied`.
- Operation returns successfully within budget: `success=True`, external outcome is `succeeded`.
- Operation returns successfully after elapsed budget: preserve `success=True` and the returned value; external outcome is `succeeded`; set `budget_exceeded=True`; emit `status=success_over_budget`; do not append retry/escalate/abstain.
- Operation throws after dispatch with uncertain side effect: external outcome is `unknown` until an independent postcondition verifier proves success or absence.
- Independent verifier proves absence and replay is unsafe: external outcome is `not_applied`; stop without replay.

## Regression gate

Required assertions:

1. late successful read preserves success/value and marks budget overrun;
2. late successful non-idempotent write performs exactly one mutation and is never reclassified or replayed;
3. pre-dispatch elapsed budget prevents the operation from running;
4. ambiguous non-idempotent timeout without verifier remains unknown and does not replay;
5. verified absence on a non-replayable operation reports not-applied;
6. telemetry emits `recovery.execution.completed` / `success_over_budget`, not `recovery.execution.stopped`, for a completed late success.

## Local focused validation

A reconstructed Python harness executed five focused tests covering all six assertions above; the telemetry assertion is part of the late non-idempotent write test. Result: 5/5 tests passed before branch publication.

Repository CI remains the authoritative exact-head validation because the execution environment used for the focused check has no direct network access to clone GitHub.

## Non-goals

This correction does not claim hard preemption of arbitrary synchronous Python callables. Transport/tool deadlines remain required and should be bounded by the remaining recovery budget. It also does not claim production readiness or external deployment evidence.
