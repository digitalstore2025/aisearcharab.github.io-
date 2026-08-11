# AISearcharab — Technical Audit

## Stack reality

The repository is not a TypeScript/React application. The production code paths are Hugo templates + browser JavaScript and a Python 3.12 FastAPI service using Pydantic, SQLAlchemy/Alembic and PostgreSQL. Therefore `any`, `@ts-ignore`, Zod, TypeScript compiler errors and npm bundle analysis are not applicable. Their Python equivalents are Pydantic boundary validation, Ruff linting, compile checks, pytest and OpenAPI drift checks.

## Findings

| Area | Finding | Severity | Action | Status |
|---|---|---:|---|---|
| Request middleware | Body ceiling was coupled to header inspection and could not prove streamed-body enforcement | High | Extracted a dedicated ASGI `RequestBodyLimitMiddleware` | PENDING_CI |
| Python lint | No explicit lint command existed in platform CI | Medium | Added pinned Ruff and dedicated security-regression lint gate | PENDING_CI |
| Unsafe source patterns | No single gate rejected privileged DOM execution sinks/browser persistence | Medium | Added `scripts/validate_secure_source.py` | PENDING_CI |
| `routes_admin.py` size | Admin route module is large and mixes user/content/source/claim workflows | Medium | Keep behavior stable in this security release; shared security policy remains centralized in `auth.py`, `audit.py`, RBAC and schemas | ACCEPTED_DEBT |
| Pagination | Public search is paginated/bounded; admin content uses a bounded `limit`; user/audit endpoints must remain operationally bounded | Medium | Existing bounds retained; production load test remains external evidence | PARTIAL |
| N+1 | Content read paths use `selectinload` for sources/claims | Low | No change | VERIFIED_BY_CODE_REVIEW |
| Dead code | Repository scan found no TODO/FIXME/placeholder runtime markers | Low | Secure-source/CI checks prevent unsafe regressions | VERIFIED_BY_CODE_SEARCH |
| Browser logs | Repository scan found no `console.log` in privileged runtime source | Low | No change | VERIFIED_BY_CODE_SEARCH |
| Error boundaries | React error boundaries do not apply | N/A | FastAPI exception/status handling and UI status rendering are the relevant mechanisms | N/A |
| Typecheck | No TypeScript exists | N/A | Pydantic models validate API inputs and response models; Python syntax compilation is mandatory | N/A |
| Coverage threshold | Existing CI executes the full API suite but no repository-wide 80% line-coverage gate is proven | Medium | Do not claim 80% without measured evidence | OPEN_NON_RELEASE_BLOCKER |
| Bundle size | No JS bundler/runtime framework exists; static site has explicit asset budgets in Hugo CI | Low | Existing static performance budget retained | VERIFIED_BY_EXISTING_CI |

## Refactoring completed

The request-size concern was removed from `SecurityHeadersMiddleware` and moved into a dedicated ASGI middleware with one responsibility: enforce a hard body ceiling even when `Content-Length` is absent. `SecurityHeadersMiddleware` now owns request IDs, response headers and privacy-minimized request logging only.

## Quality gates

The branch adds:

```text
python -m ruff check src tests scripts alembic
python scripts/validate_secure_source.py
python -m compileall -q src tests scripts alembic
python -m pytest tests/test_security.py tests/test_authorization_boundaries.py
```

The existing canonical platform workflow continues to run the full pytest suite, dependency graph audit/SBOM, PostgreSQL migrations, Arabic FTS, MFA concurrency, OpenAPI digest, Docker Compose validation and hardened container smoke test.
