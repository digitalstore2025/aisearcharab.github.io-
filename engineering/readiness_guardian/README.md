# AISearch Study — Readiness Guardian

Open-source V1 production-readiness control plane for `aisearch.study`.

## Safety boundary

Guardian can show `GO` **only** if every blocking gate is an explicitly verified `PASS`, the mandatory registry is complete, and `RELEASE-EVIDENCE` verifies the repository-authoritative `platform/apps/api/scripts/release_evidence.py` contract. Guardian never replaces that release contract.

`FAIL`, `BLOCKED`, `PENDING`, `UNKNOWN`, unverified `PASS`, missing mandatory gates, and downgraded mandatory gates all fail closed. Imported JSON is atomic: one malformed record rejects the entire import. Optional boolean fields must be real JSON booleans.

## Run locally

```bash
cd engineering/readiness_guardian
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:8080`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Docker

```bash
docker build -t aisearch-readiness-guardian .
docker run --rm -e READINESS_BIND_HOST=0.0.0.0 -p 127.0.0.1:8080:8080 aisearch-readiness-guardian
```

The host port is deliberately loopback-only.

## Live checks

The UI checks TLS, HTTPS reachability, baseline security headers, canonical URL, `/about`, `/contact`, `/privacy`, `/terms`, `/security`, `/robots.txt`, and `/sitemap.xml`. Redirects must remain on the expected HTTPS hostname and expected route. Network failures never create `PASS`.

## State isolation

Dashboard state and UI references are created inside the `@ui.page('/')` builder, so each page/client receives isolated transient state. V1 still binds to `127.0.0.1` by default and should not be exposed publicly without a separately reviewed authentication/authorization design.

## Public-repository safety

The committed seed is sanitized. Do not commit private Coda/Drive URLs, credentials, incident-only evidence, customer data, or other non-public provenance.

## Current seed decision

The supplied seed intentionally remains `NO-GO`. `RELEASE-EVIDENCE` is blocking until the authoritative release-evidence validator succeeds on the final non-PR release ref.
