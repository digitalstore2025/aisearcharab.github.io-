# Search evaluation and Arabic normalization

## Scope

AISearchArab uses the governed lexical retrieval implementation under
`platform/apps/api`. The Hugo `index.json` remains the static fallback.
This repository does not maintain a second top-level search implementation.

## Arabic normalization

The shared normalizer is intentionally conservative:

- Unicode text is normalized with NFKC and case-folding.
- Arabic diacritics and tatweel are removed.
- Common alef, ya, waw and hamza variants are normalized.
- Invisible bidirectional and zero-width formatting controls are removed.
- Ta marbuta is preserved and no stemming is applied.

Removing invisible controls prevents visually identical queries from producing
different tokens. Stop-word deletion is not applied because it can erase
meaning from short Arabic queries and is not supported by the current golden
evaluation corpus.

## Reproducible evaluation

Run:

```bash
cd platform/apps/api
python scripts/evaluate_search.py --output /tmp/search-evaluation.json
```

The evaluator uses the versioned fixtures in `tests/fixtures/` and fails
closed unless all current acceptance thresholds pass:

- MRR@10 >= 0.85
- recall@5 = 1.0
- zero-result rate = 0.0

CI uploads the JSON output as the `phase3-search-evaluation` artifact. The
artifact is test evidence for the checked revision; it is not evidence of
external runtime performance, production readiness, or horizontal scale.

## Vector-index decision

FAISS and sentence-transformers are not added by this audit. A vector index
would introduce model provenance, artifact integrity, memory, latency,
dependency, and relevance-regression obligations. Adopt one only after a
representative Arabic corpus and query set demonstrate a measured improvement
over the lexical baseline, with pinned model identity, reproducible index
metadata, security review, and explicit latency/cost budgets.
