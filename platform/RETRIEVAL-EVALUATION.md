# Retrieval Evaluation Gate

Status: offline evaluation only. Production retrieval remains the reviewed lexical/FTS path. This document does not authorize embeddings, vector search, reranking, or external crawling.

## Purpose

Any semantic, hybrid, vector, reranking, or alternate lexical implementation must beat the current baseline on a human-reviewed benchmark before it can enter Staging or Production. The comparison layer is deliberately separate from runtime retrieval so experiments cannot silently alter user-visible behavior.

## Benchmark representation

The persisted evaluation artifacts use opaque `query_id` values rather than query text. Human-readable query text may live in an access-controlled research dataset, but routine CI reports should contain only query IDs, document IDs, relevance grades, aggregate metrics, configuration/version identifiers, and timings.

Judgments use graded relevance:

- `0`: not relevant
- `1`: marginally relevant
- `2`: relevant
- `3`: highly relevant / directly answers the information need

Each judged query must have at least one document with a positive relevance grade.

Example judgments:

```json
{
  "q-0001": {
    "doc-a": 3,
    "doc-b": 1,
    "doc-c": 0
  }
}
```

Ranking files contain only ordered document identifiers:

```json
{
  "q-0001": ["doc-a", "doc-b", "doc-c"]
}
```

## Metrics

`retrieval_eval.py` computes:

- MRR@10: how early the first relevant result appears;
- Recall@5: how much judged relevant material appears in the top five;
- Precision@5: relevant density in the first five positions;
- nDCG@10: graded ranking quality using exponential relevance gain;
- Hit Rate@10: whether at least one relevant result appears in the first ten;
- Zero-result rate;
- Mean result count.

The comparison report includes candidate-minus-baseline deltas for MRR@10, nDCG@10, Recall@5, and zero-result rate.

## Offline comparison

```bash
cd platform/apps/api
python scripts/compare_retrieval.py \
  --judgments /secure/evals/judgments.json \
  --baseline /secure/evals/lexical-rankings.json \
  --candidate /secure/evals/hybrid-rankings.json \
  --output /tmp/retrieval-comparison.json
```

The default gate is fail-closed against regressions in MRR@10, Recall@5, nDCG@10, and zero-result rate. Tighter minimum improvements can be required with:

```text
--min-mrr-delta
--min-recall-delta
--min-ndcg-delta
--max-zero-result-delta
```

A candidate must not be promoted merely because one metric improves while another degrades.

## Current 20-query regression fixture

`tests/fixtures/golden_queries.json` is useful for detecting regressions in the current small corpus. It is not a sufficient human-judged benchmark for approving vector/hybrid retrieval because it was built around known fixture documents and does not represent the distribution, ambiguity, dialects, typos, entity variation, temporal questions, adversarial queries, and difficult zero-answer cases expected in production.

## Minimum evidence before a retrieval architecture change

A proposed retrieval change remains experimental until all of the following are available:

1. A substantially larger, editorially reviewed Arabic benchmark with opaque IDs and graded relevance labels.
2. A reproducible baseline/candidate run from the same corpus revision.
3. No unacceptable regression in MRR@10, Recall@5, nDCG@10, zero-result rate, citation coverage, or factual-support checks.
4. Latency and resource-cost measurements under representative concurrency.
5. Privacy review for embeddings/model providers and retention behavior.
6. Security review for any new external network path or model/tool integration.
7. Staging evidence and rollback capability.

Only after those gates pass should an implementation proposal modify the production retrieval path.
