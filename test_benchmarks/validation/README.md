# Product Validation Benchmark

This directory contains human-evaluation assets for AISearchArab product validation.

These assets are intentionally separate from automated regression tests. Passing CI is not a substitute for product validation.

## Files

- `query_set_seed.csv`: seed task bank for the first Arabic benchmark. These are prompts/tasks only, not expected answers.
- `blind_comparison_scorecard.csv`: one row per evaluator × task × AIS mode comparison.

## Protocol

1. Recruit participants from the current validation ICP: journalists, researchers, fact-checkers, and research/media intelligence professionals.
2. Prefer participant-supplied real tasks. Use the seed bank only to fill coverage gaps.
3. Capture outputs from AISearchArab and alternatives at approximately the same time for freshness-sensitive tasks.
4. Remove product branding from outputs when practical.
5. Randomize output order before scoring.
6. Do not ask evaluators which product they prefer until after usefulness/trust/citation scoring.
7. Record failures, refusals, missing evidence, and zero-result outcomes; never silently replace a weak first result with a better retry.
8. Preserve raw comparison evidence outside this public repository when it contains private participant data.
9. Where feasible, evaluate both `retrieval_only` and `generated_answer` modes so model synthesis is not confused with retrieval/evidence value.
10. Freeze the scoring rubric and decision thresholds before reviewing benchmark outcomes.

## Required score fields

- `evaluator_id`: pseudonymous identifier.
- `task_id`: stable task identifier.
- `persona`: participant role.
- `ais_mode`: `retrieval_only` or `generated_answer`.
- `query_source`: `participant` or `seed`.
- `winner`: `aisearcharab`, `chatgpt`, `perplexity`, `google`, `tie`, or `none`.
- `ais_task_success`: 0 or 1.
- `ais_retrieval_success`: 0 or 1; did the evidence layer retrieve enough relevant material to support the task?
- `ais_zero_result`: 0 or 1.
- `ais_citation_usefulness`: integer 1–5, blank if citations do not apply.
- `ais_citation_accuracy_pct`: 0–100 or blank; proportion of checked citations that support the associated claims.
- `ais_citation_completeness_pct`: 0–100 or blank; proportion of material externally verifiable claims with adequate citation support.
- `ais_groundedness_pct`: 0–100 or blank; proportion of material answer claims entailed by the reviewed evidence.
- `ais_trust`: integer 1–5.
- `ais_completion_seconds`: measured or blank.
- `would_return`: 0 or 1.
- `reason`: concise evaluator explanation.
- `notes`: evaluator/researcher notes; do not store secrets or identifying personal data.

## Measurement validity controls

The scorer refuses to emit a threshold-based operating decision until the scorecard contains at least:

- 30 comparisons;
- 10 unique evaluators;
- 10 unique tasks.

Below that level the decision is `INSUFFICIENT_EVIDENCE`.

The scorer reports descriptive 95% Wilson intervals for preference and task-success rates. These intervals do **not** fully model dependence created by repeated tasks from the same evaluator. For a publication-quality study, analyse evaluator-level clustering or use an appropriate hierarchical/clustered model.

Always inspect mode slices. A high `generated_answer` score with weak `retrieval_only` performance is evidence that the model layer may be masking corpus/retrieval weakness rather than proving a durable information advantage.

## Bias controls

- Do not tell evaluators that the purpose is to prove AISearchArab is better.
- Do not discard difficult tasks.
- Do not retry only AISearchArab when the first output is weak.
- Do not change evaluation criteria after seeing which system wins.
- Report ties and `none` outcomes.
- Report unusable/missing comparisons.
- Do not infer product-market fit from seeded questions alone; report the participant-query share.
- Keep freshness-sensitive comparisons within the same capture window.

## Scoring

Human-readable report:

```bash
python scripts/score_product_validation.py test_benchmarks/validation/blind_comparison_scorecard.csv
```

Machine-readable report:

```bash
python scripts/score_product_validation.py test_benchmarks/validation/blind_comparison_scorecard.csv --json
```

## Decision discipline

The initial thresholds in `docs/PRODUCT-VALIDATION-GATE-2026-09.md` are proposed operating thresholds and should be recalibrated only if the pilot demonstrates that the measurement instrument itself is unreliable—not because the observed result is inconvenient.

The first batch is a measurement pilot, not product-market-fit evidence.
