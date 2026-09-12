# RAG metrics reference

Retrieval candidates: Recall@k, Precision@k, MRR, nDCG, evidence coverage.
Generation candidates: factual correctness, faithfulness/groundedness, citation precision/recall, completeness, abstention quality.
Operational metrics: p50/p95 latency, token usage, retrieval cost, generation cost, failure rate.

A high answer score cannot compensate for systematic retrieval misses. Keep per-stage metrics visible.
