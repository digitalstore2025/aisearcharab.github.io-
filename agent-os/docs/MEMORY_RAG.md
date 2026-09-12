# Memory and RAG contract

Memory namespaces: `session`, `project`, `preferences`, `verified_knowledge`.

A memory item can guide behavior without being a factual source. Treat it as a factual claim only when it is verified, unexpired, and its source is appropriate to the decision.

RAG pipeline target:
`query -> lexical/vector retrieval -> metadata filtering -> dedupe -> rerank -> freshness weighting -> contextual compression -> answer -> citation verification`.

Recommended metrics: Recall@K, MRR, NDCG, citation precision, faithfulness, answer completeness, freshness, and latency/cost per successful answer.
