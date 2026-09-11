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

- `AISEARCH_API_BASE_URL` is read only under `src/server/`.
- Browser code never receives the upstream API base URL.
- Only HTTPS origins are accepted, except reviewed local/container hosts (`localhost`, `127.0.0.1`, `api`).
- User input can change query parameters, never protocol/host/path of the upstream.
- Requests have a 4.5 second timeout and `cache: no-store`.
- Search failures do not fall back to an LLM or third-party service.
- Raw search queries are not logged by the web layer.

## Contract

The TypeScript response parser mirrors FastAPI `SearchResponse` and `SearchResult`. `scripts/audit_api_contract.py` parses the backend Pydantic source using Python AST and fails CI if required fields or key route constraints drift.

## Search UX

Search state uses URL parameters (`q`, `page`). Submission is a plain GET form, so no Client Component or per-keystroke request is required. Results stream under a component-level `Suspense` boundary. Pagination uses server-generated `Link` URLs.

## Deliberate divergence from the tutorial

The official tutorial connects Next.js directly to PostgreSQL because it has no existing API boundary. This repository already has a hardened FastAPI/PostgreSQL service, so duplicating DB access in Next.js would create two authorization/data-access implementations and increase drift risk.
