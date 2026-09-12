# Orchestration Foundation

Status: integrated internal execution layer. It does not add a public endpoint, external fetching, embeddings, reranking, autonomous publishing, or a new workflow vendor dependency. The public grounded-answer contract remains unchanged; its internal control flow is now explicit and deterministically validated.

## Why this exists

AISearcharab already has governed lexical retrieval, reviewed claims, grounded answer generation, quota enforcement, evidence revalidation, RBAC/MFA, and GEO evidence handling. Multi-step AI/research execution is now represented as explicit domain steps before any durable runtime is introduced.

The local orchestration module implements five reusable patterns inspired by the Vercel AI SDK workflow examples:

1. Sequential workflow
2. Parallel workers
3. Routing
4. Orchestrator/worker
5. Evaluator/refinement loop

The implementation is dependency-free and synchronous so domain behavior remains portable and can be tested independently of a workflow vendor.

## Safety invariants

- No orchestration trace stores payloads, query text, evidence text, secrets, session values, or CSRF values.
- Parallel workers must not share a SQLAlchemy `Session`; each database-backed worker must own an independent session.
- Routing can select only a pre-registered handler.
- Orchestrator plans can select only pre-registered workers.
- Normalized route/worker name collisions fail closed.
- Evaluator loops have a hard ceiling of 10 evaluations and default to 3.
- Grounded response validation is deterministic; another LLM is not used as the grounding judge.
- No automatic external fetch is introduced.
- No embeddings or reranking are enabled.
- No new public endpoint or response field is introduced.
- Existing auth, CSRF, quota, reviewed-claim and post-provider evidence-revalidation boundaries remain in force.

## Integrated grounded-answer workflow

`POST /v1/answers/grounded` now executes the governed lifecycle as explicit internal steps:

```text
request
→ authentication / authorization / CSRF
→ retrieve_evidence
→ release_read_transaction
→ reserve_generation_quota
→ generate_claim_selection
→ validate_grounded_contract
→ revalidate_evidence
→ audit result
→ response
```

The deterministic `validate_grounded_contract` postcondition checks that:

- `request_id` is preserved end-to-end;
- the server reports the expected retrieval provenance;
- selected `evidence_id` and `claim_key` values exist in the immutable evidence snapshot;
- duplicate selected claim references are rejected;
- citations match the selected evidence provenance exactly;
- an `insufficient` result cannot carry selected claims or citations;
- the endpoint fails closed before returning a malformed grounded result.

Evidence is still revalidated against the database after provider latency. Concurrent edit/archive/review changes therefore invalidate the response rather than allowing a stale evidence snapshot to escape.

## Golden retrieval gate

The fixture-backed lexical Golden Dataset was expanded from 7 to 20 Arabic/English-mixed queries across five current corpus topics:

- GPT-5 Arabic analysis
- model comparison
- OpenAI API development
- OSINT image verification
- AI/children safety

The existing evaluation workflow remains the gate: MRR@10 must be at least `0.85`, Recall@5 must be `1.0`, and zero-result rate must remain `0.0`.

This fixture is a regression dataset, not yet a sufficient real-world human-judged benchmark for approving vector search or reranking. A broader editorially reviewed query set is still required before changing retrieval architecture.

## Durable runtime decision

Do not bind core research logic directly to Vercel Workflow, Inngest, Temporal, or another runtime yet. Keep domain steps as ordinary Python callables. A future adapter may wrap these steps only after:

- staging latency/error evidence exists;
- idempotency boundaries are documented;
- retryable vs fatal failures are classified;
- side-effecting steps have idempotency keys;
- observability is externalized;
- rollback/recovery behavior is tested.

This keeps the FastAPI/Python domain model portable while preserving a clean migration path to durable execution.

## External research and hybrid retrieval gates

External research workers remain blocked until there is a general-purpose network policy with explicit allowlists, SSRF protection, redirect validation, DNS/IP controls, response-size ceilings and timeouts.

Embeddings, vector search and reranking remain experimental-only until a human-reviewed Golden Dataset and reproducible lexical-vs-hybrid comparison demonstrate a measurable gain without unacceptable citation, latency, privacy or cost regressions.

## Next gated work

1. Add payload-free OpenTelemetry spans for orchestration step names and durations.
2. Expand the Golden Dataset with real, human-judged Arabic information needs and graded relevance labels.
3. Build an offline lexical-vs-hybrid evaluation harness without changing production retrieval.
4. Document idempotency keys and retry/fatal classifications for every future side-effecting step.
5. Exercise the explicit grounded workflow in Staging and collect latency/error evidence.
6. Evaluate a durable runtime adapter only after the preceding gates pass.
7. Add external research workers only after the network-security gate is independently reviewed.
