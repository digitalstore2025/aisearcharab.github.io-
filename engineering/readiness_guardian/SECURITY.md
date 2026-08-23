# Security Policy

## Purpose

Readiness Guardian is an internal decision-support and evidence-registry application. It must not itself become an authority that can silently enable production.

## Security invariants

1. Production is `GO` only when every blocking gate is exactly `PASS`.
2. `FAIL`, `BLOCKED`, `PENDING`, and `UNKNOWN` are fail-closed states.
3. Imported data is untrusted input and must pass strict validation.
4. A `PASS` state is not a verified pass unless evidence is explicitly marked verified.
5. Live-check network errors never produce `PASS`.
6. No production API key belongs in the client, repository, tests, logs, or documentation.
7. The dashboard must remain separated from production feature-flag mutation.
8. Authentication and authorization are required before public exposure.

## Deployment requirements

- Place the app behind TLS.
- Add HSTS, `X-Content-Type-Options: nosniff`, a restrictive `Referrer-Policy`, and clickjacking protection (`frame-ancestors` in CSP or `X-Frame-Options`).
- Use the hosting provider's secret manager/environment facility.
- Prefer SSO/OIDC or an authenticated reverse proxy for internal access.
- Preserve audit logs for imported evidence and release decisions if write workflows are added.
- Do not add a production activation button without a separate approved authorization design.

## Public-repository constraint

The committed seed is sanitized. Do not commit private Coda/Drive URLs, credentials, incident-only evidence, customer data, or other non-public provenance into this public repository.

## Reporting

Treat all findings as unverified until reproduced against the relevant revision or deployment.
