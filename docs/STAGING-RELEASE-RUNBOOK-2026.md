# AISearcharab.com — Staging Release Runbook 2026

## Purpose

This runbook turns the repository gates into an operational Staging release procedure. It is intentionally provider-neutral. Production deployment is not authorized by this document and remains blocked until the acceptance gates in `PERFECT-MASTER-2026.md` are independently evidenced.

## 1. Required Staging topology

Staging must use the same responsibility boundaries intended for production:

- one HTTPS frontend origin;
- one HTTPS API origin or same-origin API route;
- managed PostgreSQL with a dedicated Staging database/user;
- external secrets delivery; no secrets committed to Git;
- edge controls capable of distributed rate limiting/WAF before production;
- external log/metric collection before production approval.

Do not use SQLite for Staging. Do not run multiple migration writers concurrently.

## 2. Required environment controls

Set at minimum:

```text
APP_ENV=staging
DATABASE_URL=postgresql+psycopg://<staging-user>:<secret>@<host>/<db>
ALLOWED_ORIGINS=https://<frontend-staging-origin>
ALLOWED_HOSTS=<api-staging-host>
API_PREFIX=/v1
MAX_SEARCH_LIMIT=20
SEARCH_CANDIDATE_LIMIT=300
LOG_SEARCH_QUERIES=false
SESSION_TTL_MINUTES=720
SESSION_IDLE_MINUTES=30
STEP_UP_TTL_MINUTES=10
LOGIN_MAX_FAILURES=5
LOGIN_LOCK_MINUTES=15
PASSWORD_MIN_LENGTH=14
MAX_REQUEST_BODY_BYTES=524288
ENFORCE_SEPARATION_OF_DUTIES=true
```

If query logging is explicitly enabled for a reviewed test, provide a random `QUERY_HASH_KEY` of at least 32 bytes and define retention/access rules before enabling it.

`STEP_UP_TTL_MINUTES` controls the short-lived current-password re-authentication window for privileged mutations. Keep it between 2 and 30 minutes and shorter than the absolute session TTL. It is not a replacement for production MFA/WebAuthn.

## 3. Pre-deployment gate

Release only a commit whose final-base CI is green for both site and platform workflows. Record:

```text
release_commit=<40-char SHA>
site_workflow_run=<run id>
platform_workflow_run=<run id>
openapi_digest=<expected digest>
runtime_dependency_graph_digest=<expected digest>
```

Verify that the platform run includes successful dependency-drift, hash-audit, PostgreSQL migration/Arabic FTS, schema-drift and container-smoke gates.

## 4. Database change procedure

1. Take/verify a recoverable Staging backup or snapshot according to the managed database provider.
2. Ensure no second migration job is active.
3. Run the migration job once:

```bash
alembic upgrade head
alembic current
```

4. The expected revision for this release line is:

```text
20260807_0004
```

5. Verify `admin_sessions.elevated_until` exists after migration.
6. Do not start accepting Staging traffic if `/health/ready` reports a schema revision mismatch.

## 5. API deployment verification

After the migration and API deployment:

```bash
curl --fail --silent --show-error https://<api-staging-host>/health/live
curl --fail --silent --show-error https://<api-staging-host>/health/ready
curl --fail --silent --show-error https://<api-staging-host>/v1/meta/capabilities
```

Required behavior:

- liveness succeeds;
- readiness succeeds only on the expected migration revision;
- capabilities continue to report generated answers/payments/crawling as disabled unless a separately approved release changes them;
- API documentation/OpenAPI endpoints remain disabled when `APP_ENV=production`; Staging exposure must still be access-reviewed.

## 6. Security header and host checks

Check representative API/admin responses. At minimum validate:

- `Strict-Transport-Security` in Staging/Production;
- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- restrictive `Content-Security-Policy`;
- `Cache-Control: no-store` for API/admin/auth;
- `X-Robots-Tag: noindex, nofollow` for API/admin;
- valid `X-Request-ID` correlation;
- untrusted Host values are rejected.

Do not put authentication cookies, tokens, raw search queries or request/response bodies into release evidence.

## 7. Editorial governance and privileged-auth smoke test

Use three non-production identities representing creator, reviewer and publisher. Verify:

1. creator creates draft, source and claim;
2. creator cannot approve their own review when separation of duties is enabled;
3. reviewer approves claim and content;
4. reviewer cannot perform the final publication if they are already the reviewer;
5. publisher login alone is denied when attempting final publication with `step-up authentication required`;
6. publisher performs `POST /v1/auth/step-up` with a valid CSRF token and their current password, then publication succeeds inside the configured window;
7. after `elevated_until` expires, another privileged operation is denied until re-authentication occurs again;
8. invalid step-up passwords return generic invalid-credentials behavior and contribute to the existing account lockout policy;
9. owner user-management mutations similarly require step-up;
10. published item becomes searchable;
11. a reviewed item edited before publication is demoted and requires review again;
12. audit entries contain `auth.step_up` success/failure records plus actor/request correlation without password, token or cookie values.

Delete or archive test content after evidence is captured. Do not capture the entered password in screenshots, logs or release records.

## 8. Search quality and load evidence

Repository fixture metrics are regression checks, not launch evidence. Build a human-reviewed Arabic query set and retain it outside public logs when it includes sensitive terms.

Run the aggregate-only load probe:

```bash
cd platform/apps/api
python scripts/load_probe.py \
  --base-url https://<api-staging-host> \
  --queries /secure/path/arabic-benchmark.json \
  --requests 1000 \
  --concurrency 25 \
  --max-p95-ms 750 \
  --max-error-rate 0.01
```

Record only the aggregate JSON output. The probe intentionally does not print query text or response bodies.

For production approval, use a benchmark large enough to report MRR@10, NDCG@10, Recall@5/10, Precision@5, zero-result rate and segment metrics alongside P50/P95/P99 latency.

## 9. Observability acceptance

Before calling the release `TESTED_IN_STAGING`, verify:

- structured application request events arrive in the external log sink;
- request IDs can correlate a client failure to an application event;
- no raw query/token/cookie/body leakage appears in sampled logs;
- latency/error dashboards operate for the Staging API;
- at least one synthetic alert is triggered and routed to the intended recipient/runbook.

## 10. Rollback

Application rollback and database rollback are separate decisions.

Application rollback:

1. stop new rollout;
2. redeploy the previously recorded known-good image/commit;
3. verify `/health/live`, `/health/ready`, capabilities and representative search/admin paths;
4. record the rollback commit/image and incident reason.

Database rollback:

- Prefer forward-fix migrations when safe.
- Never run an Alembic downgrade in production-like data merely to match an old image without first proving data compatibility.
- If a destructive/incompatible migration requires restore, use the tested managed-database restore procedure and validate consistency before reopening traffic.

A production approval requires an actual rollback/restore drill, not only this written procedure.

## 11. Promotion decision

Use the project status vocabulary exactly. Staging deployment alone is not `PRODUCTION_READY`.

Promotion beyond `TESTED_IN_STAGING` requires independent security/accessibility evidence, real search-quality evidence, managed backup/restore evidence, distributed rate limiting/WAF, production-grade privileged-account MFA/WebAuthn or another independently reviewed second factor, external observability, DNS/TLS/live-header verification and explicit human release approval. The implemented password step-up is a defense-in-depth control and must not be represented as MFA.
