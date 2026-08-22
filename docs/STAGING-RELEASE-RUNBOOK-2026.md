# AISearcharab.com — Staging Release Runbook 2026

## Purpose

This runbook turns the repository gates into an operational Staging release procedure. It is intentionally provider-neutral. Production deployment is not authorized by this document and remains blocked until the acceptance gates in `PERFECT-MASTER-2026.md` are independently evidenced.

## Deployment governance invariant

Production publishing is explicit and human-triggered. GitHub Pages deployment is permitted only from `refs/heads/main`; a workflow dispatch from a feature or pull-request branch may build for diagnostics but must not upload or deploy the production Pages artifact. A successful internal static artifact is not external Staging evidence.

Provider integrations such as Vercel remain `BLOCKED` whenever the deployment status is failed, build logs are inaccessible to the authorized release operator, or no independently reachable HTTPS preview can be verified. Do not add provider-specific configuration merely to make a status green without first identifying and reproducing the build failure.

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
ALLOWED_HOSTS=<exact-api-staging-host>
API_PREFIX=/v1
MAX_SEARCH_LIMIT=20
SEARCH_CANDIDATE_LIMIT=300
LOG_SEARCH_QUERIES=false
SESSION_TTL_MINUTES=720
SESSION_IDLE_MINUTES=30
STEP_UP_TTL_MINUTES=10
LOGIN_MAX_FAILURES=5
LOGIN_LOCK_MINUTES=15
LOGIN_THROTTLE_KEY=<secret-manager value, minimum 32 random bytes>
PASSWORD_MIN_LENGTH=14
MAX_REQUEST_BODY_BYTES=524288
ENFORCE_SEPARATION_OF_DUTIES=true
REQUIRE_MFA_FOR_PRIVILEGED=true
MFA_ENCRYPTION_KEY=<secret-manager value, minimum 32 random bytes>
MFA_ENROLLMENT_TTL_MINUTES=10
MFA_ISSUER=AISearcharab.com
```

`ALLOWED_HOSTS` must list exact Staging API hostnames. Do not use `*` or wildcard-subdomain patterns such as `*.example.com` in Staging/Production.

If the API is behind a reverse proxy, set `TRUSTED_PROXY_CIDRS` only to the explicit ingress/proxy networks actually controlled by the deployment. Leave it empty when no trusted proxy network has been verified. Never use `/0` or an aggregate set that trusts an entire IP family.

If query logging is explicitly enabled for a reviewed test, provide a random `QUERY_HASH_KEY` of at least 32 bytes and define retention/access rules before enabling it.

`MFA_ENCRYPTION_KEY` and `LOGIN_THROTTLE_KEY` must come from the Staging secret manager or protected environment injection. Never place real values in Git, screenshots, CI comments or release evidence. The application uses the MFA key to protect TOTP secrets at rest and the throttle key to derive privacy-preserving pre-authentication throttle identities.

`STEP_UP_TTL_MINUTES` controls a separate short-lived current-password re-authentication window for privileged mutations. Keep it between 2 and 30 minutes and shorter than the absolute session TTL. Password Step-up is defense-in-depth in addition to TOTP MFA; it is not itself MFA.

## 3. Pre-deployment gate

Release only a commit whose final-base CI is green for both site and platform workflows. Record:

```text
release_commit=<40-char SHA>
site_workflow_run=<run id>
platform_workflow_run=<run id>
openapi_digest=<expected digest>
runtime_dependency_graph_digest=<expected digest>
```

Verify that the platform run includes successful dependency-drift, hash-audit, PostgreSQL migration/Arabic FTS, MFA tests, schema-drift and container-smoke gates.

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
20260816_0008
```

5. Verify the schema includes the MFA state introduced by `20260808_0005`:

```text
users.mfa_secret_encrypted
users.mfa_pending_secret_encrypted
users.mfa_pending_expires_at
users.mfa_enabled_at
users.mfa_last_counter
admin_sessions.mfa_verified_at
mfa_recovery_codes
```

6. Verify `20260816_0006` added the persistent pre-authentication throttle state:

```text
login_throttles
ix_login_throttles_updated_at
```

7. Verify `20260816_0007` added GEO tenancy structures:

```text
organizations
organization_memberships
geo_projects
```

8. Verify `20260816_0008` added GEO query/evidence structures:

```text
geo_query_sets
geo_queries
geo_provider_runs
geo_evidence_snapshots
geo_mentions
geo_citations
```

9. Verify `users.mfa_last_counter` has no permanent server default after migration; the temporary `-1` default is migration-only to backfill existing rows.
10. Do not start accepting Staging traffic if `/health/ready` reports a schema revision mismatch.
11. The release-evidence record for a `PRODUCTION_READY` candidate must identify the same `20260816_0008` revision; a custom/stale migration identifier is not acceptable production evidence.

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
- untrusted Host values are rejected;
- wildcard and wildcard-subdomain host configuration is rejected before Staging/Production startup.

Do not put authentication cookies, tokens, TOTP secrets, recovery codes, raw search queries or request/response bodies into release evidence.

## 7. MFA and privileged-auth smoke test

Use non-production privileged accounts. At minimum include `owner` and `publisher`.

1. Log in with password only. Confirm the privileged session cannot access `/v1/auth/me` or admin APIs and receives `multi-factor authentication required` until the second factor completes.
2. For a new account, start enrollment with current-password confirmation and valid CSRF. Confirm the returned TOTP secret is not present in application logs or database plaintext.
3. Enroll the TOTP secret in an independent authenticator and confirm a current code.
4. Confirm the session gains MFA verification only after a valid code.
5. Log out and log in again. Confirm password login alone remains insufficient and a current TOTP code is required.
6. Attempt replay of a TOTP value already accepted for that user. It must be rejected.
7. Use one recovery code. It must work once; replay of the same recovery code must be rejected.
8. Confirm recovery-code database records contain digests, not plaintext recovery values.
9. Regeneration of recovery codes must require both a completed MFA session and Password Step-up; old unused recovery codes become invalid after regeneration.
10. When `REQUIRE_MFA_FOR_PRIVILEGED=true`, attempting to disable MFA for `owner`, `admin` or `publisher` must be rejected.
11. Invalid MFA attempts return generic invalid-code behavior, contribute to account lock policy, and eventually revoke the current session when the configured threshold is reached.
12. Audit events record factor success/failure/recovery use without TOTP secret, OTP value, recovery code, password, cookie or token material.

Do not store screenshots showing TOTP seeds or recovery codes as release evidence. Evidence should record only success/failure, actor/test identity, request correlation and timestamps.

## 8. Editorial governance and Password Step-up smoke test

Use three non-production identities representing creator, reviewer and publisher. Verify:

1. creator creates draft, source and claim;
2. creator cannot approve their own review when separation of duties is enabled;
3. reviewer approves claim and content;
4. reviewer cannot perform the final publication if they are already the reviewer;
5. after publisher MFA verification, final publication is still denied until Password Step-up is completed;
6. publisher performs `POST /v1/auth/step-up` with a valid CSRF token and current password, then publication succeeds inside the configured window;
7. after `elevated_until` expires, another privileged operation is denied until re-authentication occurs again;
8. invalid step-up passwords return generic invalid-credentials behavior and contribute to the existing account lockout policy;
9. owner user-management mutations similarly require MFA plus step-up;
10. published item becomes searchable;
11. a reviewed item edited before publication is demoted and requires review again;
12. audit entries contain `auth.step_up` and MFA events plus actor/request correlation without password, token, cookie, OTP or recovery-code values.

Delete or archive test content after evidence is captured. Do not capture entered credentials or factors in screenshots, logs or release records.

## 9. Search quality and load evidence

Repository fixture metrics are regression checks, not launch evidence. Build a human-reviewed Arabic query set and retain it outside public logs when it includes sensitive terms. Production Release Evidence requires at least 500 reviewed queries before `search.benchmark_verified=true` is eligible.

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

For production approval, report MRR@10, NDCG@10, Recall@5/10, Precision@5, zero-result rate and segment metrics alongside P50/P95/P99 latency.

## 10. Observability acceptance

Before calling the release `TESTED_IN_STAGING`, verify:

- structured application request events arrive in the external log sink;
- request IDs can correlate a client failure to an application event;
- no raw query/token/cookie/body/TOTP/recovery-code leakage appears in sampled logs;
- latency/error dashboards operate for the Staging API;
- at least one synthetic alert is triggered and routed to the intended recipient/runbook.

## 11. Rollback

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

## 12. Promotion decision

Use the project status vocabulary exactly. Staging deployment alone is not `PRODUCTION_READY`.

TOTP MFA is a code-level control and must be proven in the real Staging environment and included in the independent security review. Promotion beyond `TESTED_IN_STAGING` additionally requires independent accessibility evidence, real search-quality evidence, managed backup/restore evidence, distributed rate limiting/WAF, external observability, DNS/TLS/live-header verification, rollback evidence, verified branch governance and explicit human release approval.
