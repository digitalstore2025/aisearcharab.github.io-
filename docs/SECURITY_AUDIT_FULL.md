# AISearcharab — Full Security Audit

Audit target: `main` after merge `cf2ddb76149b07a4b3214082e9102e7e8e5b7946`, plus hardening branch `audit/ultimate-a-to-z-2026-08-11`.

Actual stack: Hugo + browser JavaScript, FastAPI/Python 3.12, Pydantic, SQLAlchemy/Alembic, PostgreSQL, Docker Compose, GitHub Actions.

| Layer | Problem / attack | Severity | File / surface | Reproduction / evidence | Impact | Fix | Status |
|---|---|---:|---|---|---|---|---|
| Frontend | DOM XSS through dangerous HTML execution sinks | High if present | `platform/apps/api/src/aisearcharab_api/admin_static/admin.js`, `static/js/search.js` | Repository search found no `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `eval`, `new Function`; regression test scans privileged JS | Session/admin compromise | DOM construction remains `textContent`/DOM APIs; CI rejects dangerous sinks | FIXED_PENDING_CI |
| Frontend | CSP bypass / inline execution | High if permissive | `middleware.py` | Admin CSP contains no `unsafe-inline`/`unsafe-eval`; API defaults to `default-src 'none'` | Script execution | CSP tightened with `object-src 'none'`, `worker-src 'none'`, `frame-src 'none'`, `base-uri 'none'` | FIXED_PENDING_CI |
| Frontend | Token persistence in LocalStorage | High if present | Admin console | Repository scan found no `localStorage`/`sessionStorage`; opaque session is HttpOnly cookie | Token theft persistence | Secure source gate forbids privileged browser storage | FIXED_PENDING_CI |
| API | IDOR/BOLA on privileged resources | High | `/v1/admin/users/{id}`, editorial routes | RBAC dependencies precede mutation; new regression creates an editor, permits draft creation, denies owner mutation | Cross-user privilege abuse | Existing RBAC/CSRF/step-up retained; explicit negative BOLA test added | FIXED_PENDING_CI |
| API | Request-body limit bypass through chunked transfer | High | ASGI request pipeline | Prior implementation checked only `Content-Length`; chunked bodies could bypass that pre-check | Memory/CPU DoS and oversized parser input | Dedicated ASGI `RequestBodyLimitMiddleware` buffers only to configured hard ceiling and rejects streamed overage with 413 | FIXED_PENDING_CI |
| API | SSRF | N/A current surface | Source metadata | No `httpx`, `requests`, `urllib/urlopen`, `aiohttp` outbound fetch path found; source URLs are stored, not fetched | None in current runtime | No outbound-fetch capability is exposed | VERIFIED_BY_CODE_SEARCH |
| API | Distributed abuse/rate limiting | Release blocker | Edge + API | Application has account lockout and bounded search; no distributed edge/WAF evidence exists | Distributed brute force / resource abuse | Must be provided and tested in Staging before production; release evidence already fails closed on this control | EXTERNAL_BLOCKED |
| Database | Browser/service-role database bypass | High if present | DB connectivity | No Supabase service role or browser DB credential found; DB access is server-only | Direct table bypass | Keep DB credentials server-side only; secret scanning remains enforced | VERIFIED_BY_CODE_SEARCH |
| Database | PostgreSQL RLS absent | Medium defense-in-depth | PostgreSQL | No `CREATE POLICY` / RLS migration found | Backend compromise would retain DB-role authority | Current model relies on API RBAC and private DB role. RLS is not claimed; no direct client DB surface exists | ACCEPTED_ARCHITECTURE_LIMIT |
| Auth | Session fixation | High | `/v1/auth/login` | Login creates new random session + CSRF secrets and stores only digests | Session takeover | Opaque fresh token per login; old supplied token is not reused | VERIFIED_BY_CODE_REVIEW |
| Auth | CSRF on mutations | High | Admin/auth/MFA mutation routes | `require_mutation`, `require_sensitive_mutation`, `require_csrf` compare CSRF digest with constant-time HMAC | Unauthorized state changes | SameSite=Strict + double-submit-style CSRF binding + explicit header | VERIFIED_BY_TEST_SUITE |
| Auth | Privileged MFA bypass | High | owner/admin/publisher | `get_principal` requires completed MFA for privileged roles when configured | Privilege compromise | TOTP + recovery + replay protection remain mandatory in staging/production configuration | VERIFIED_IN_CI_CODE_PATH; STAGING_PENDING |
| Storage | MIME spoof / malicious SVG / CSV / GeoJSON | N/A current surface | `/v1/admin/upload` | No upload endpoint or storage adapter exists; adversarial request receives 404 | No file persistence attack surface | Keep absent until a separately reviewed file service exists | FIXED_PENDING_CI |
| Infra | Missing hardening headers | Medium | API/admin responses | Existing headers plus new DNS prefetch/origin isolation controls | Browser policy weakening | `nosniff`, DENY framing, CSP, referrer, permissions, COOP/CORP, HSTS in secure env, no-store | FIXED_PENDING_CI |
| Infra | Host/CORS confusion | High | `config.py`, middleware | Explicit origins/hosts; wildcard forbidden in production; untrusted Host test exists | Cache poisoning / cross-origin credential abuse | TrustedHost + strict origin parser + credentialed explicit CORS | VERIFIED_BY_TEST_SUITE |
| Supply chain | Unpinned actions/dependencies | High | GitHub Actions, Python runtime | Core Actions and container image use immutable SHAs/digests; runtime dependency graph hash + SBOM/VEX audit | Build compromise | Existing supply-chain gates retained; new Ruff dependency is dev-only and pinned | PENDING_CI_AUDIT |
| Supply chain | `npm audit` | N/A | Repository | No Node package manifest/runtime dependency tree exists | None | Do not add npm solely for auditing a non-Node stack | N/A |
| Secrets | Secrets committed in Git/history | Critical if present | Repository/history | Existing working-tree and reachable-history scanners run in CI | Credential compromise | Existing secret scanners retained; workflow checkout has `persist-credentials: false` | VERIFIED_BY_EXISTING_CI |

## Adversarial tests added

- streamed/chunked body exceeds `MAX_REQUEST_BODY_BYTES` → `413`;
- privileged admin JavaScript contains no executable HTML sinks;
- mismatched MIME malicious SVG sent to absent upload endpoint → `404`;
- newly created editor completes allowed draft-creation journey;
- the same editor cannot PATCH the owner account → `403`;
- admin CSP rejects inline/eval/object execution patterns;
- hardened runtime exposes required headers through `curl -I`.

## Launch classification

Code-level hardening does not change the external release vocabulary. Until HTTPS Staging, distributed edge limits/WAF, managed PostgreSQL/PITR/restore, external observability, independent security/accessibility review and rollback evidence exist, the release remains `INTEGRATED_NOT_TESTED` / production blocked.
