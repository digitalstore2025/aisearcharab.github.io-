# Security review reference

Use selectively.

- Identity: authentication strength, session/token lifecycle, MFA assumptions.
- Authorization: object/function-level checks, tenant isolation, default-deny behavior.
- Input/data: validation, canonicalization, injection, unsafe parsing/deserialization.
- Web: XSS, CSRF, SSRF, CORS/CSP, redirects, file upload/download boundaries.
- Secrets/crypto: secret storage, rotation, accidental logging, encryption in transit/at rest.
- AI/tooling: prompt injection, untrusted tool output, excessive tool permissions, data exfiltration.
- Supply chain: vulnerable dependencies, lockfiles, provenance, install scripts, CI permissions.
- Operations: rate limiting, abuse controls, audit logs, incident visibility, rollback.

Severity requires both credible impact and plausible reachability/preconditions.
