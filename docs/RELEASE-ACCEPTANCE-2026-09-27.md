# Release acceptance execution — 2026-09-27

Baseline: da1ecc56a9e7b75beb862c6cd57ee21d23538235. Production: BLOCKED.

## Executed in this change

- Fix deployment discovery validation to follow the explicit HTTPS build base while preserving canonical identity validation.
- Exercise AI-search discovery on a project-pages subpath in CI.
- Fail fast during Pages build/validation.
- Add four regression tests: accepted project path, rejected wrong link, rejected canonical identity substitution, rejected HTTP.
- Local validation: 18 unit tests passed; structured data and sensitive-data scan passed.
- Public staging probe attempted from the execution environment: DNS resolution failed before reaching the target. This is an environment failure, not evidence of service downtime. No load workload was started.

## Remaining acceptance gates

Owners below are proposed roles, not confirmed assignments. Suggested numerical targets are proposals, not approved service commitments.

| Gate | Acceptance evidence | Proposed owner | State |
|---|---|---|---|
| Hugo deployment | Required CI passes on candidate; Pages uses GitHub Actions and deploys validated Hugo artifact; live revision matches | Repository admin / DevOps | Pending external Pages configuration and deployment |
| Staging | Fixed-target preflight validates exact revision, database binding, TLS, Host policy, headers, health, generated answers disabled | DevOps | Blocked by execution DNS; Render workspace confirmed; runtime configuration is stale |
| Bounded load | Existing contract: 40 requests, concurrency 4, zero errors, p95 <=2500ms, p99 <=5000ms, max <=8000ms | SRE | Not run; requires passing preflight |
| Capacity | Define expected peak requests/sec and representative workload first. Proposed: peak 60min, 2x peak 15min, soak 8h, all within agreed SLO | Product owner / SRE | No production workload or infrastructure confirmed |
| Recovery | Proposed RPO <=15min and RTO <=60min; isolated restore and integrity verification, plus deployed release rollback | DBA / SRE | External evidence required |
| Security | Current candidate reviewed; no unresolved Critical/High findings; deployed auth/MFA/tenant/rate-limit negative tests | Security reviewer | CI controls partial; independent review missing |
| Accessibility | Applicable WCAG 2.2 AA criteria on core journeys, keyboard and screen reader evidence | Accessibility reviewer / QA | External review required |
| Observability | Trace known synthetic event end-to-end; proposed alert delivery <=5min; verify actual recipient acknowledgment | SRE | External evidence required; no alert messages sent |
| Governance | Protect main; require validated site/API/security checks; review before merge; prove failing PR cannot merge | Repository admin | Branch observed unprotected; no configuration mutation performed |

Each evidence record must identify source SHA, deployment/image digest where applicable, environment, UTC timestamp, command, exit code, immutable artifact reference, checksum, reviewer and scope limitations. CI success, mock results and bounded staging load must never be promoted to production-capacity evidence.

Use existing release_evidence.py controls; do not mark controls true merely because this acceptance document exists. Preserve PRODUCTION_READY=false until all required controls and evidence references pass the release model.

## Render control-plane verification — 2026-09-27

Workspace confirmed by owner: My Workspace. Service aisearcharab-api-staging-v2 (srv-da143mjl550s73epk8m0) is still configured as a Python service, auto-deploy off, no health-check path. This differs from render.yaml's Docker runtime, checksPass trigger and /health/ready health check.

Latest listed deploy: 5038d680300c8039031a0ec2e17500cb6924dda1, build_failed on September 13. The listed live deploy remains 32c4bfa6f0e6681dc4a33cba4442ae0202aaad1f from September 12; it does not prove execution of the September 26 load harness.

Old database aisearcharab-staging-db is suspended (billing), expired September 15. Replacement aisearcharab-staging-db-v2 is available, free, HA disabled, expires October 23. Its existence does not prove service binding, migration state, PITR or restore readiness.

The connected Render tools expose service reads, deploy triggers and environment-variable updates, but no service runtime/build/Blueprint update action. Do not trigger another deploy against the obsolete contract. Dashboard access is required to reconcile the runtime and verify the database binding without exposing credentials. No paid resource was created and no secret was rotated.
