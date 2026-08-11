# AISearcharab — Known Limitations

These are verified boundaries of the current release, not planned capabilities disguised as implemented features.

1. No external HTTPS Staging deployment has been proven for the final `main` release line.
2. Distributed rate limiting/WAF/API-gateway behavior is not yet externally verified.
3. Managed PostgreSQL PITR, backup/restore and measured RPO/RTO evidence are not attached.
4. External secrets management and external observability/alert routing are not yet evidenced.
5. PostgreSQL RLS is not implemented because the current architecture has no direct browser/client database access; authorization is enforced in the server API.
6. No file-upload/storage feature exists. Image re-encoding, magic-byte validation and signed object URLs are therefore not product capabilities.
7. No outbound crawler/fetcher exists, so SSRF-capable URL retrieval is not a current runtime surface.
8. No TypeScript/React/Node runtime exists; TypeScript/Zod/npm-specific gates are not applicable to this stack.
9. Repository search regression fixtures are not production search-quality evidence. Release evidence requires a human-reviewed Arabic benchmark of at least 500 queries.
10. No independent WCAG 2.2 AA, browser matrix or live Lighthouse report is attached to the current release.
11. No independent external security assessment is attached to the current release.
12. Production remains blocked until Issue #14 external gates are evidenced and a human Go/No-Go is recorded.
