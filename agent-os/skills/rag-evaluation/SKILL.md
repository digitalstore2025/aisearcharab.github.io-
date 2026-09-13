---
name: rag-evaluation
description: Measure retrieval, grounding, citation, or answer quality for a RAG system or compare variants.
---

Use when evaluating an existing/proposed RAG pipeline, not for generic LLM prompting.

- Define the evaluation unit and gold/acceptable evidence.
- Separate retrieval metrics from generation metrics.
- Include adversarial/no-answer cases and corpus coverage failures.
- Compare variants on the same frozen dataset where possible.
- Report quality, latency, and cost separately; avoid collapsing them into one opaque score.

Read `references/metrics.md` when selecting metrics.
