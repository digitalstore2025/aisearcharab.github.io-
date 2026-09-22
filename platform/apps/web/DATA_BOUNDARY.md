# Web Data Boundary — Chapters 6–10

## Decision

The Next.js application does **not** open a second PostgreSQL connection or duplicate the backend ranking logic. `platform/apps/api` remains the system of record for PostgreSQL, migrations, published-content filtering, Arabic normalization and lexical ranking.

Data flow:

```text
Browser
→ Next.js page / Server Components
→ fixed server-side API client
→ FastAPI /v1/search
→ PostgreSQL / ranking layer
```

## Security invariants

- Search is disabled by default and requires `AISEARCH_SEARCH_ENABLED=true` plus a reviewed API origin.
- `AISEARCH_API_BASE_URL` is read only under `src/server/`.
- Browser code never receives the upstream API base URL.
- Only HTTPS origins are accepted, except reviewed local/container hosts (`localhost`, `127.0.0.1`, `api`).
- User input can change query parameters, never protocol/host/path of the upstream.
- Outbound search requests reject redirects, time out after 4.5 seconds, and use `cache: no-store`.
- Upstream search bodies are capped at 256 KiB before JSON parsing and validated against bounded TypeScript contracts.
- API content links must remain canonical local absolute paths; backslashes, encoded separators, query strings, fragments and cross-origin resolution are rejected at both API and web boundaries.
- Search failures do not fall back to an LLM or third-party service.
- Application code does not log raw search queries. Deployment access logs must independently redact query-string parameter `q` before production search is enabled.

## Contract

The TypeScript response parser mirrors FastAPI `SearchResponse` and `SearchResult`. `scripts/audit_api_contract.py` parses the backend Pydantic source using Python AST and fails CI if required fields or key route constraints drift. The backend also validates search-result URL paths so legacy or malformed database values fail closed instead of becoming browser navigation targets.

## Search UX

Search state uses URL parameters (`q`, `page`). Submission is a plain GET form, so no Client Component or per-keystroke request is required. Results stream under a component-level `Suspense` boundary. Pagination uses server-generated `Link` URLs.

Because URL state is intentionally shareable, the application sends `Referrer-Policy: no-referrer` to prevent the query from leaking through navigation. Browser history and infrastructure request logs remain separate privacy surfaces and must be covered by deployment policy.

## Deliberate divergence from the tutorial

The official tutorial connects Next.js directly to PostgreSQL because it has no existing API boundary. This repository already has a hardened FastAPI/PostgreSQL service, so duplicating DB access in Next.js would create two authorization/data-access implementations and increase drift risk.
