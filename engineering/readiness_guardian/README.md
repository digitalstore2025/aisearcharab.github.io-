# AISearch Study — Readiness Guardian

Open-source V1 production-readiness control plane for `aisearch.study`.

## Architecture

```text
Evidence snapshot / imported JSON
          │
          ▼
   Python readiness engine
          │
          ├── strict validation
          ├── fail-closed decision
          ├── KPI computation
          ├── invariant evaluation
          └── CSV/JSON export
          │
          ▼
       NiceGUI
          ├── GO / NO-GO
          ├── gate matrix + filters
          ├── evidence dialog
          ├── next-action queue
          ├── Arabic RTL toggle
          ├── live domain/TLS/header checks
          └── import/export
```

## Core safety invariant

Production is `GO` **only** if every blocking gate is an explicitly verified `PASS`, and the mandatory blocking-gate registry is complete. `FAIL`, `BLOCKED`, `PENDING`, `UNKNOWN`, unverified `PASS`, missing mandatory gates, and downgraded mandatory gates all fail closed.

Imported JSON is atomic: one malformed record rejects the entire import. Optional boolean fields must be real JSON booleans.

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

## Live domain checks

The UI can check TLS, HTTPS reachability, baseline security headers, canonical URL, `/about`, `/contact`, `/privacy`, `/terms`, `/security`, `/robots.txt`, and `/sitemap.xml`. Redirects must remain on the expected HTTPS hostname. Network failures never create `PASS`.

## Data contract

The sanitized seed is `data/snapshot.json`. Supported statuses are `PASS`, `FAIL`, `BLOCKED`, `PENDING`, and `UNKNOWN`.

Required gate fields are `id`, `category`, `gate`, `status`, `blocking`, and `evidence`. Optional fields are `source`, `acceptance` / `acceptanceCriteria`, `next_action` / `nextAction`, `verified`, and `trust_surface` / `trustSurface`.

## Deployment boundary

V1 is a **single-operator internal tool** and binds to `127.0.0.1` by default. Do not expose the process directly to a network. Multi-user/shared deployment is out of scope until the transient process-global state is replaced by per-user/session storage and authentication/authorization is independently reviewed.

## Security notes

- No API keys are embedded.
- The dashboard never flips production feature flags.
- Do not expose V1 publicly.
- Runtime secrets belong in a secret manager/environment, not source control.
- The committed seed is sanitized and contains no private Coda/Drive URL.
- Do not treat dashboard state as authoritative without evidence provenance.

## Current seed decision

The supplied seed intentionally remains `NO-GO` until unresolved blocking gates are independently verified.
