# PR #137 corrective acceptance criteria

This document defines the merge gate for the late-completion semantic correction.

## Required behavior

| Scenario | Expected external outcome | Expected local result | Replay |
| --- | --- | --- | --- |
| budget exhausted before dispatch | `not_applied` | safe stop | none |
| call returns success within budget | `succeeded` | success | none |
| call returns success after elapsed budget | `succeeded` | success + `budget_exceeded=true` | none |
| non-idempotent timeout with uncertain side effect and no verifier | `unknown` | safe stop | none |
| uncertain side effect verified present | `succeeded` | success | none |
| uncertain side effect verified absent and replay not allowed | `not_applied` | safe stop | none |

## Merge gate

Do not merge unless the exact head passes:

- Agent OS unit tests;
- focused late-completion contract tests;
- static control-plane evals;
- controlled reliability benchmark;
- live Toxiproxy reliability gate;
- OpenTelemetry verification;
- installed-wheel verification;
- reproducible release archive check;
- repository quality/governance workflows;
- automated review with no unresolved correctness finding on late-completion semantics.

A green CI run proves conformance to the checked repository contracts only. It does not establish production capacity or safe hard preemption of arbitrary synchronous calls.
