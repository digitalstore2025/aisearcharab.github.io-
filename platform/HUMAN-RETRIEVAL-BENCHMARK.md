# Human Retrieval Benchmark Gate

Status: tooling and promotion contract only. This file does not claim that a human-reviewed benchmark already exists.

## Purpose

The neural stress test is useful engineering evidence, but synthetic questions over a tiny fixture cannot authorize a production retrieval migration. A production decision requires editorially independent relevance judgments tied to a pinned corpus revision.

## Secure authoring model

The authoring dataset may be maintained in an access-controlled research workspace. CI-facing inputs must use opaque identifiers only; raw query text is intentionally rejected by `retrieval_judgments.py`.

Each query entry contains:

- an opaque `query_id`;
- locale: `ar`, `en`, `tr`, or `mixed`;
- document judgments from at least two independent annotators;
- optional adjudications for disagreements.

Grades are:

- `0`: not relevant;
- `1`: marginally relevant;
- `2`: relevant;
- `3`: directly/highly relevant.

The same annotator cannot adjudicate a disagreement they participated in.

## Fail-closed finalization

`finalize_retrieval_judgments.py` refuses to emit promotable judgments when:

- query/document/annotator IDs are malformed;
- query text or unsupported fields are included in the CI artifact;
- a query or annotation is duplicated;
- a document has fewer than two independent judgments;
- relevance grades fall outside 0..3;
- a disagreement lacks independent adjudication;
- an adjudicator is one of the original annotators;
- an adjudication contradicts unanimous annotations;
- a finalized query has no positively relevant document.

## Agreement evidence

The tool computes pairwise linearly weighted Cohen's kappa across annotators with overlapping items, exact agreement, disagreement counts, adjudication counts, annotation counts and query counts. The default promotion gate requires:

- at least 100 finalized queries;
- at least two annotators;
- zero unresolved disagreements;
- mean weighted kappa of at least 0.60.

These are minimum engineering gates, not a substitute for editorial review of sampling quality. A benchmark can pass agreement statistics and still be biased or unrepresentative.

## Outputs

The finalizer writes two artifacts:

1. evaluator judgments: `query_id -> document_id -> grade` plus corpus revision;
2. agreement evidence: aggregate counts, pairwise agreement metrics, thresholds and pass/fail state.

Neither output contains raw query text.

Example execution after the secure human-review dataset has actually been collected:

```bash
cd platform/apps/api
python scripts/finalize_retrieval_judgments.py \
  --input /secure/evals/human-annotations.json \
  --judgments-output /tmp/human-judgments.json \
  --evidence-output /tmp/human-agreement.json \
  --min-queries 100 \
  --min-kappa 0.60
```

Only the finalized judgment artifact should feed lexical-vs-neural/hybrid comparisons. Synthetic fixtures remain separate and must not be relabeled as human-reviewed evidence.

## Sampling requirements before production decisions

The eventual benchmark should include Modern Standard Arabic, dialect variation, Arabic/English code switching, transliteration, typos, entity aliases, temporal questions, multi-document information needs, ambiguous queries, genuinely unanswerable queries, adversarial wording, and source-quality conflicts. Query sampling should come from a reviewed production-like distribution rather than being generated solely around known documents.
