# Orchestration Foundation

Status: internal foundation only. This module is not exposed as a public API, does not enable external fetching, embeddings, reranking, or autonomous publishing, and does not change the production gate for generated answers.

## Why this exists

AISearcharab already has governed lexical retrieval, reviewed claims, grounded answer generation, quota enforcement, evidence revalidation, RBAC/MFA, and GEO evidence handling. The next architectural step is to make multi-step AI/research execution explicit before introducing a durable runtime.

The local orchestration module implements five patterns inspired by the Vercel AI SDK workflow examples:

1. Sequential workflow
2. Parallel workers
3. Routing
4. Orchestrator/worker
5. Evaluator/refinement loop

The implementation is dependency-free and synchronous so it can be tested independently of any workflow vendor.

## Safety invariants

- No orchestration trace stores payloads, query text, evidence text, secrets, session values, or CSRF values.
- Parallel workers must not share a SQLAlchemy `Session`; each worker that needs database access must own an independent session.
- Routing can select only a pre-registered handler.
- Orchestrator plans can select only pre-registered workers.
- Evaluator loops have a hard ceiling of 10 evaluations and default to 3.
- No automatic external fetch is introduced.
- No embeddings or reranking are introduced.
- No public endpoint is introduced.
- No existing grounded-answer or search behavior is changed.

## Intended mapping

### Current grounded answer path

```text
request
→ authenticated/authorized endpoint
→ lexical retrieval
→ reviewed-claim bounding
→ persistent quota reservation
→ provider claim selection
→ server-side rendering
→ post-provider evidence revalidation
→ audit result
```

This remains the production-safe path.

### Future research workflow

After staging evidence is available, orchestration can evolve toward:

```text
query
→ deterministic router
→ retrieval workers
→ evidence normalization
→ claim selection
→ evaluator
→ bounded refinement
→ citation/integrity gate
→ response
```

Parallel execution should be reserved for independent operations. Database-backed workers must use separate sessions or process-local repositories.

## Durable runtime decision

Do not bind core research logic directly to Vercel Workflow, Inngest, Temporal, or another runtime yet. Keep domain steps as ordinary Python callables. A future adapter can wrap these steps in a durable runtime after:

- staging latency/error evidence exists;
- idempotency boundaries are documented;
- retryable vs fatal failures are classified;
- side-effecting steps have idempotency keys;
- observability is externalized;
- rollback behavior is tested.

This keeps the FastAPI/Python domain model portable while allowing a durable executor to be added later.

## Next integration candidates

1. Extract the existing grounded-answer route into explicit domain steps without changing its HTTP contract.
2. Add deterministic evaluator checks for citation/evidence integrity.
3. Add OpenTelemetry spans around orchestration names only, never raw query/evidence payloads.
4. Build a benchmark comparing the current linear path with orchestrated execution.
5. Only then evaluate a durable runtime and, separately, vector/hybrid retrieval against the Golden Dataset.
