# Neural Retrieval Experiment

Status: offline experiment only. This directory does not alter production retrieval, API contracts, database schema, or runtime dependencies.

## Goal

Measure whether a multilingual neural retriever materially improves difficult Arabic/cross-lingual retrieval over AISearch's current transparent lexical baseline before any vector or hybrid path is proposed for Staging.

The first executable candidate is `intfloat/multilingual-e5-base` at revision `f7d866c89004f9c578631ccaca8bb7b28e7315f2`. It is MIT licensed, multilingual, uses an XLM-R encoder and has a materially smaller footprint than the larger BGE-M3 candidate. The experiment uses the model's required `query:` and `passage:` prefixes.

BGE-M3 remains a higher-capability candidate for a later run because it supports dense, sparse and multi-vector retrieval in one multilingual model. It is intentionally not the first CI candidate because its larger artifact/runtime cost would obscure whether the benchmark and release gate themselves work correctly.

## Challenge set

`challenge_queries.json` contains 40 synthetic stress queries over the existing five published fixture documents. It deliberately includes:

- Arabic paraphrases with weak lexical overlap;
- Arabic/English cross-lingual queries;
- noisy Latin text and typos;
- semantic reformulations;
- privacy, API-security, OSINT and model-comparison concepts.

This set is useful for engineering regression and smoke evaluation. It is **not** a substitute for the planned human-reviewed Arabic benchmark and must not by itself authorize a production retrieval migration.

## Reproducible comparison

The benchmark:

1. loads the same reviewed fixture documents used by the API search tests;
2. ranks them with the current production lexical scorer;
3. loads the pinned multilingual embedding model with `trust_remote_code=False`;
4. generates normalized dense embeddings;
5. ranks documents by cosine-equivalent dot product;
6. compares baseline and candidate with the shared `retrieval_eval` metrics;
7. emits only aggregate metrics/model metadata, not query text;
8. fails CI unless the candidate improves MRR@10, Recall@5 and nDCG@10 by at least 0.05 and does not worsen zero-result rate.

Run locally from the repository root after installing the isolated experiment requirements:

```bash
python -m pip install -e platform/apps/api
python -m pip install -r platform/experiments/neural_retrieval/requirements.txt
python platform/experiments/neural_retrieval/run_benchmark.py --output /tmp/neural-retrieval-report.json
```

## Promotion boundary

A successful experiment is evidence that the candidate deserves deeper evaluation; it is not a production approval. Promotion still requires a substantially larger human-reviewed benchmark, corpus-version pinning, privacy review, latency and memory measurements under representative concurrency, storage/index design, citation-support checks, Staging rollback evidence and a security review of any embedding service/network path.
