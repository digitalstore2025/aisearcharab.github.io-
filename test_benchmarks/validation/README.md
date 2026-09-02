# Product Validation Benchmark

This directory contains human-evaluation assets for AISearchArab product validation.

These assets are intentionally separate from automated regression tests. Passing CI is not a substitute for product validation.

## Files

- `query_set_seed.csv`: seed task bank for the first Arabic benchmark. These are prompts/tasks only, not expected answers.
- `blind_comparison_scorecard.csv`: one row per evaluator × task comparison.

## Protocol

1. Recruit participants from the current validation ICP: journalists, researchers, fact-checkers, and research/media intelligence professionals.
2. Prefer participant-supplied real tasks. Use the seed bank only to fill gaps and maintain coverage.
3. Capture outputs from AISearchArab and relevant alternatives at approximately the same time for freshness-sensitive tasks.
4. Remove product branding from outputs when practical.
5. Randomize output order before scoring.
6. Do not ask evaluators which product they prefer until after they score usefulness/trust/citations.
7. Record failures, refusals, missing evidence, and zero-result outcomes; do not silently replace them with a better retry.
8. Preserve the raw evidence used for each scored comparison outside this repository when it includes private participant data.

## Required score fields

- evaluator_id: pseudonymous identifier.
- task_id: stable task identifier.
- persona: participant role.
- winner: `aisearcharab`, `chatgpt`, `perplexity`, `google`, `tie`, or `none`.
- ais_task_success: 0 or 1.
- ais_citation_usefulness: integer 1–5, blank if no citations apply.
- ais_trust: integer 1–5.
- ais_completion_seconds: measured or blank.
- would_return: 0 or 1.
- reason: concise evaluator explanation.
- notes: evaluator/researcher notes; do not store secrets or identifying personal data.

## Bias controls

- Do not tell evaluators that the purpose is to prove AISearchArab is better.
- Do not discard difficult tasks.
- Do not retry only AISearchArab when the first output is weak.
- Do not change evaluation criteria after seeing which system wins.
- Report ties and `none` outcomes.
- Report the number of unusable/missing comparisons.

## Decision discipline

The initial thresholds in `docs/PRODUCT-VALIDATION-GATE-2026-09.md` are proposed operating thresholds and should be recalibrated after the pilot if the measurement instrument itself proves unreliable.

The first batch is a measurement pilot, not product-market-fit evidence.
