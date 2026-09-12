# Execution Contracts

Status: architecture and runtime-safety contract for multi-step AI/research work. These rules apply before any durable workflow runtime is introduced.

## Replay classes

Every step that may later be wrapped by a durable executor must be classified before retries are enabled.

### `PURE_REPLAY_SAFE`

Deterministic computation with no external side effect. Examples: local schema validation, claim/citation postconditions, ranking metric calculation, routing over already-materialized inputs.

Automatic retry is safe when the same bounded input is supplied.

### `READ_REPLAY_SAFE`

Read-only access whose result may legitimately change between attempts. Examples: retrieval, evidence lookup, current-state checks.

Retries are allowed, but the caller must decide whether it requires the original snapshot or a fresh read. Snapshot/revision provenance must be preserved when correctness depends on the original state.

### `IDEMPOTENT_SIDE_EFFECT`

A side effect that can be retried only when a stable idempotency key is enforced by the destination or repository. Examples can include a quota reservation or audit write keyed by `request_id` if the storage layer guarantees duplicate suppression/consistent semantics.

No durable runtime may assume idempotency merely because a function name contains `record`, `reserve`, `upsert`, or `create`.

### `NON_IDEMPOTENT_SIDE_EFFECT`

Actions such as sending a message, publishing content, charging a payment method, issuing a credential, or creating an external resource when duplicate execution is harmful.

These steps must not receive automatic retries until an explicit idempotency mechanism exists. High-impact actions additionally require authorization and, where policy requires it, human approval.

## Failure classes

### `TRANSIENT_RETRYABLE`

Temporary provider/network failures, connection resets, selected 5xx responses, or rate limits with bounded backoff. Retry counts and deadlines must be finite.

### `CONFLICT_RETRY_FROM_FRESH_STATE`

Optimistic-lock conflicts or evidence changing while a provider request is in flight. The current execution must fail closed; a new attempt must reacquire current state rather than replaying a stale snapshot.

### `POLICY_FATAL`

Authentication/authorization failures, disabled features, exhausted quota, prohibited network destinations, or approval rejection. These are not repaired by retrying the same operation.

### `VALIDATION_FATAL`

Malformed structured output, unknown claim/evidence identifiers, impossible provenance, unregistered routes/workers, schema violations, or deterministic integrity-gate failures. Retrying the same payload without a deliberate recovery policy is not allowed.

### `OPERATOR_INTERVENTION`

Infrastructure or governance states that require a human/operator decision: failed migration evidence, backup/restore failures, missing secret-management configuration, external-security-review blockers, or ambiguous partial side effects.

## Current grounded-answer mapping

| Step | Replay class | Failure policy |
| --- | --- | --- |
| retrieve reviewed evidence | `READ_REPLAY_SAFE` | retry only with explicit fresh/snapshot semantics |
| release read transaction | `PURE_REPLAY_SAFE` from workflow perspective | fatal only on local runtime defect |
| reserve generation quota | `IDEMPOTENT_SIDE_EFFECT` only under its persistent request/user reservation semantics | quota exhaustion is `POLICY_FATAL`; DB transient failure is bounded retry only if duplicate reservation is impossible |
| provider claim selection | external read-like computation, no AISearcharab side effect | transient provider failures may retry within configured provider bounds; invalid output is `VALIDATION_FATAL` |
| deterministic grounded contract validation | `PURE_REPLAY_SAFE` | `VALIDATION_FATAL` |
| evidence revalidation | `READ_REPLAY_SAFE` | changed evidence is `CONFLICT_RETRY_FROM_FRESH_STATE` |
| generation audit result | side effect requiring stable request identity | audit failure must not silently change the answer's factual contract; operational policy decides retry/export behavior |

The current path performs no autonomous publishing, payments, outbound messaging, or arbitrary tool execution.

## Durable-runtime admission criteria

A workflow-runtime adapter for Vercel Workflow, Inngest, Temporal, or another engine may be proposed only when:

1. Every wrapped step has a documented replay class and failure class.
2. Side-effecting steps have proven idempotency keys or are explicitly excluded from automatic retry.
3. Retry counts, deadlines, backoff and cancellation behavior are bounded.
4. Human-approval boundaries are defined for consequential actions.
5. Payload-free tracing is available independently of the runtime vendor.
6. Crash/restart tests demonstrate recovery from checkpoints without duplicated side effects.
7. Staging demonstrates rollback and incident handling.
8. Secrets, PII, evidence text and raw user queries are excluded from routine workflow metadata unless an explicitly reviewed policy authorizes them.

## Agent/tool rule

An LLM may suggest a plan or select among registered capabilities, but it does not expand its own permissions. The application must validate every route, worker, tool argument, tenant boundary, authorization requirement and output contract server-side before an action executes.
