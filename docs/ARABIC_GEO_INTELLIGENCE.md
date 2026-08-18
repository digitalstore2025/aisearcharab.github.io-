# Arabic GEO Intelligence

Status: implementation branch
Branch: `feature/arabic-geo-intelligence`

## Goal
Build an evidence-first B2B GEO intelligence module that measures brand/entity visibility across AI answer systems and search without presenting fabricated model knowledge, citations, or scores as facts.

## Product boundaries

The module distinguishes four different phenomena:

1. Search visibility.
2. AI answer mentions.
3. AI answer citations.
4. Provider/model preference under a defined test set.

No single metric may be labeled as a universal "AI ranking".

## Core domain

- Organization / workspace
- Project
- Domain / entity
- Competitor
- Query set
- Query
- Provider run
- Answer evidence
- Mention
- Citation
- Source snapshot
- Metric observation
- Score snapshot
- Finding
- Recommendation
- Audit event

Every tenant-owned object must carry an organization/workspace identifier and authorization must be enforced server-side on resource access.

## Evidence contract

A provider run is immutable after completion and records:

- stable UUID
- project and query IDs
- provider adapter identifier
- model/version when exposed by the provider
- execution timestamp in UTC
- normalized prompt/query
- raw response hash
- answer text or protected evidence reference
- extracted mentions
- extracted citations
- execution status and failure class

Scores are derived from stored evidence only. Provider output is untrusted input.

## Scoring v0

The first deterministic score is intentionally narrow and reproducible:

`visibility_score = 100 * (0.45 * mention_rate + 0.35 * citation_rate + 0.20 * source_diversity_rate)`

Where each component is normalized to [0, 1] over a declared query set and provider/run window.

The API must return component values and sample size next to the aggregate score. A score with insufficient evidence must be marked `insufficient_data`, not extrapolated.

## Security requirements

### URL and crawler safety
- allow only http/https
- reject embedded credentials
- reject localhost and loopback destinations
- reject private, link-local, multicast, reserved and unspecified IP ranges
- resolve DNS and re-check every connection target to mitigate DNS rebinding
- enforce redirect limits and revalidate redirect destinations
- enforce response byte/time limits
- prohibit arbitrary schemes and file access

### AI/provider safety
- provider keys remain server-side
- provider adapters receive bounded, typed requests
- web/page content is treated as untrusted data, never system instructions
- indirect prompt injection must not alter tool permissions or execution policy
- citations must be extracted and validated independently of generated prose where possible
- raw provider responses and evidence require retention/access policy

### SaaS controls
- RBAC: owner/admin/analyst/viewer
- tenant isolation on reads and writes
- audit logs for security-sensitive mutations
- rate limits and quotas
- request size limits
- CSRF protection for cookie-authenticated mutations
- secret scanning and dependency review in CI

## API surface v0

- `POST /api/v1/geo/projects`
- `GET /api/v1/geo/projects/{project_id}`
- `POST /api/v1/geo/projects/{project_id}/domains`
- `POST /api/v1/geo/projects/{project_id}/competitors`
- `POST /api/v1/geo/projects/{project_id}/query-sets`
- `POST /api/v1/geo/query-sets/{query_set_id}/queries`
- `POST /api/v1/geo/query-sets/{query_set_id}/runs`
- `GET /api/v1/geo/runs/{run_id}`
- `GET /api/v1/geo/projects/{project_id}/citations`
- `GET /api/v1/geo/projects/{project_id}/competitors/compare`
- `GET /api/v1/geo/projects/{project_id}/scores`
- `GET /api/v1/geo/projects/{project_id}/recommendations`

Mutation endpoints require authenticated membership and role checks.

## Provider adapter boundary

Providers must implement a small internal interface rather than leaking SDK-specific logic into routes:

```python
class ProviderAdapter(Protocol):
    provider_id: str

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        ...
```

No browser/client receives provider credentials.

## Delivery gates

The feature is not mergeable until all are true:

- migrations reviewed
- tenant-isolation tests pass
- RBAC negative tests pass
- SSRF test corpus passes
- score determinism tests pass
- malformed provider output tests pass
- no fabricated seed metrics in production paths
- OpenAPI schema validates
- lint/type/test CI passes
- database migration upgrade/downgrade verified
- security review completed

## Implementation order

1. Domain models + migrations.
2. Authorization policy helpers.
3. URL/SSRF validator.
4. Query sets and immutable provider-run evidence.
5. Provider adapter interface and one non-production fake adapter used only in tests.
6. Citation/mention extraction contract.
7. Deterministic scoring service.
8. Recommendations from measurable findings.
9. API routes and OpenAPI schemas.
10. Tests, migration verification, CI and security review.
