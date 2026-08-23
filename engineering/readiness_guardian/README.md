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
          │
          ├── GO / NO-GO
          ├── KPI cards
          ├── gate matrix + filters
          ├── evidence dialog
          ├── next-action queue
          ├── Arabic RTL toggle
          ├── live domain/TLS/header checks
          └── import/export
```

## Core safety invariant

Production is `GO` **only** if every `blocking=True` gate is exactly `PASS`.

`FAIL`, `BLOCKED`, `PENDING`, and `UNKNOWN` all block production.

Imported JSON is strictly validated. Malformed states are rejected rather than coerced.

## Run locally

```bash
cd engineering/readiness_guardian
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
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
docker run --rm -p 8080:8080 aisearch-readiness-guardian
```

## Live domain checks

The UI includes an explicit **Run live domain checks** action for TLS certificate validation, HTTPS reachability, baseline security headers, canonical URL, and the public trust/search surfaces `/about`, `/contact`, `/privacy`, `/terms`, `/security`, `/robots.txt`, and `/sitemap.xml`.

Network failures never create a PASS state.

## Data contract

The seed lives at `data/snapshot.json`. Supported statuses are `PASS`, `FAIL`, `BLOCKED`, `PENDING`, and `UNKNOWN`.

Required fields per gate:

```json
{
  "id": "SEC-REG",
  "category": "Security",
  "gate": "Security regression",
  "status": "PENDING",
  "blocking": true,
  "evidence": "Current-head pass not verified."
}
```

Optional fields: `source`, `acceptance` / `acceptanceCriteria`, `next_action` / `nextAction`, `verified`, and `trust_surface` / `trustSurface`.

## Deployment boundary

This is an internal engineering control-plane tool, not part of the public Hugo surface. NiceGUI is intentionally scoped to this directory and must not be added to the public-site runtime. Deploy only behind authentication on a container-capable internal service.

## Security notes

- No API keys are embedded.
- This dashboard is a decision aid; it never flips production feature flags.
- Authentication and authorization are mandatory before network exposure.
- TLS/security headers belong at the reverse proxy/edge layer.
- Runtime secrets belong in the hosting provider's secret manager/environment.
- Do not treat dashboard state as authoritative without evidence provenance.

## Current seed decision

The supplied evidence snapshot intentionally remains `NO-GO` until unresolved blocking gates are independently verified and changed to `PASS`.