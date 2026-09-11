# AISearchArab Web — Security Test Matrix

This matrix links threat classes to executable controls and evidence. A control without an automated or external evidence source is not considered complete.

| Threat / failure mode | Preventive control | Regression / verification | Evidence gate |
| --- | --- | --- | --- |
| Cross-origin URL confusion | local-path validation in API + web, resolved-origin re-check | API tests + `tests/search-security.test.ts` | Platform API + Platform Web |
| Encoded separator bypass | reject encoded `/` and `\\`, query, fragment, controls | API regression tests | Platform API |
| SSRF / redirect pivot | fixed server-only origin; no user host/path; `redirect: 'error'` | search security unit tests | Platform Web |
| Search unexpectedly enabled | explicit `AISEARCH_SEARCH_ENABLED=true` required | fail-closed unit + Playwright test | Platform Web |
| Query length/page abuse | parser and direct server-call validation | request + security tests | Platform Web |
| Oversized upstream response | 256 KiB content-length + streamed byte cap | declared and undeclared oversized-body tests | Platform Web |
| Slow upstream | abort timeout | code invariant + staging latency test | Platform Web + external staging evidence |
| Malformed/mismatched API response | runtime parser + request/response invariant checks | contract tests + Python AST contract audit | Platform Web |
| Contract drift in FastAPI | AST-based Pydantic/route marker verification | `audit_api_contract.py` | Platform Web triggered by API source changes |
| XSS sink introduced | React escaping + dangerous-sink Python scan | `audit_structure.py` | Platform Web |
| Inline handler injection | CSP `script-src-attr 'none'` | E2E response-header assertion | Platform Web |
| Clickjacking | CSP `frame-ancestors 'none'` + X-Frame-Options | E2E header assertion | Platform Web |
| Referrer query leakage | `Referrer-Policy: no-referrer` | E2E header assertion | Platform Web |
| Search prefetch/privacy leakage | `prefetch={false}` on query-bearing pagination | Python release audit | Platform Web |
| Secret/client boundary leak | Client component budget + `process.env` / `@/server` rejection | `audit_structure.py` | Platform Web |
| Unauthorized mutation surface | reject `use server` and unapproved API routes | `audit_release_gates.py` | Platform Web |
| Auth-control drift | verify FastAPI HttpOnly, SameSite, CSRF, throttle, MFA, step-up markers | `audit_release_gates.py` + backend tests | Platform Web + Platform API |
| Vulnerable dependency graph | frozen lockfile + Moderate advisory threshold | `pnpm audit --audit-level moderate` | Platform Web |
| Dependency lifecycle abuse | reviewed pnpm `allowBuilds` list | frozen install + structural audit | Platform Web |
| CI action compromise/drift | pinned GitHub Action commit SHAs | Python release audit | Platform Web |
| Static-analysis blind spot | CodeQL JS/TS + Python, `security-extended` | CodeQL jobs | CodeQL + branch protection |
| Accidental indexing before launch | robots metadata + robots.txt + X-Robots-Tag | Playwright + release audit | Platform Web |
| Visual accessibility regression | WCAG AA token calculation | `audit_design.py` | Platform Web |
| Auth proxy source-IP collapse | auth BFF remains forbidden | release audit; Issue #96 evidence before opening | External gate |
| Search abuse / volumetric DoS | search disabled by default | Issue #98: WAF/rate/load/alert evidence | External gate |
| CI bypass / unsafe merge | protected `main`, required checks, code-scanning protection | Issue #97 proof | External GitHub admin gate |

## Test ownership

- `scripts/audit_structure.py`: structure, secrets, client/server boundary, dangerous sinks, patched baselines.
- `scripts/audit_design.py`: identity and WCAG contrast.
- `scripts/audit_api_contract.py`: FastAPI search/local-path contract drift.
- `scripts/audit_release_gates.py`: release invariants, CSP/search/auth/CI/supply-chain gates.
- `tests/*.test.ts`: unit and security boundary tests.
- `e2e/foundation.spec.ts`: browser-visible headers, RTL/navigation, fail-closed search, noindex.
- FastAPI tests: authentication, governance, mutations, publishing, URL-path validation.
- CodeQL: cross-file/data-flow static security analysis.

## Required rule

Every newly fixed security defect must add at least one regression test or machine-enforced audit rule before the fix is considered complete. If a defect cannot be tested in code, the PR must identify the external evidence owner and acceptance artifact.
