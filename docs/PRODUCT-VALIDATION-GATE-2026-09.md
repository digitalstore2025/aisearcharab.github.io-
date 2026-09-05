# AISearchArab Product Validation Gate — September 2026

Status: **ACTIVE — PROCEED WITH VALIDATION GATE**

This gate exists to prevent engineering progress from being mistaken for product validation.

## Decision rule

No major feature expansion should be treated as priority work unless it does at least one of the following:

1. removes a blocker to real-user validation;
2. measurably improves retrieval, grounding, citation quality, or task success;
3. addresses a verified security/reliability blocker required to run the validation safely.

All other work is secondary until the first validation cycle is reviewed.

## Current thesis

AISearchArab is an Arabic-first AI research and intelligence product whose intended differentiation is not a generic chat interface. The intended advantage is the combination of Arabic specialization, structured evidence, provenance, editorial governance, retrieval, citations, and grounded answers.

The highest-risk unvalidated question is:

> In which exact job-to-be-done does a target user prefer AISearchArab over the tool they already use?

## Initial ICP for validation

The first validation cycle narrows the audience to users for whom evidence provenance is materially valuable:

- journalists and investigative journalists;
- researchers and fact-checkers;
- media/research intelligence professionals.

General consumers, developers, students, and broad enterprise personas are not excluded from the long-term product. They are intentionally deprioritized for this validation cycle to reduce confounding variables.

## Evidence states

Every decision must classify claims as one of:

- `FACT`: directly evidenced.
- `INFERENCE`: reasonable interpretation of evidence.
- `ASSUMPTION`: untested belief.
- `UNKNOWN`: insufficient information.
- `CONTRADICTED`: current evidence opposes the claim.
- `NOT_YET_VALIDATED`: plausible, but lacks sufficient user/market evidence.

## Existential assumptions under test

1. Target users have a frequent enough problem around Arabic AI research and source verification.
2. AISearchArab can beat general-purpose alternatives on at least one repeatable research task.
3. Source provenance and citation quality materially affect user preference.
4. The corpus covers enough real questions to produce useful answers.
5. A narrow ICP returns to the product without prompting.
6. At least one reachable buyer or user segment has credible willingness to pay.
7. The product remains valuable even when generated answers are disabled; retrieval/evidence must carry independent value.

## Measurement validity gate

The benchmark instrument must be valid before its outputs can drive product decisions.

The automated scorer must return `INSUFFICIENT_EVIDENCE` unless the collected scorecard contains at least:

- 30 evaluated comparisons;
- 10 unique evaluators;
- 10 unique tasks.

These are pilot minimums, not claims of statistical sufficiency for every inference.

Preference and task-success rates must be reported with descriptive 95% confidence intervals. Repeated tasks from the same evaluator create clustered observations, so simple binomial confidence intervals must not be described as a complete inferential model.

The collection schema must record whether AISearchArab was evaluated in `retrieval_only` or `generated_answer` mode. Retrieval success, zero-result behavior, citation accuracy, citation completeness, and groundedness must be recorded separately when applicable. This prevents generated prose from masking a weak evidence layer.

Thresholds are frozen before viewing outcomes. A disappointing result is not grounds to redefine the metric post hoc.

## Validation Experiment A — Blind Competitive Benchmark

### Hypothesis

For a defined Arabic AI research job, target users will prefer AISearchArab over their existing general-purpose alternatives because evidence traceability improves task completion and trust.

### Sample

- 20 target users.
- 3–5 real tasks per user.
- Minimum 60 evaluated task comparisons for the primary cycle.
- The 30-comparison / 10-evaluator / 10-task rule is only the minimum measurement-pilot floor.

### Competitor set

At minimum:

- AISearchArab;
- ChatGPT;
- Perplexity;
- Google Search where the task naturally fits search.

When feasible, evaluators should not see product names while scoring outputs.

### Metrics

- Blind Preference Rate.
- Task Success Rate.
- Retrieval Success Rate.
- Zero-result Rate.
- Citation Usefulness, 1–5.
- Citation Accuracy.
- Citation Completeness.
- Groundedness.
- Trust, 1–5.
- Completion time.
- Return intent.
- Qualitative reason for preference.
- Participant-supplied query share.

### Proposed decision thresholds

These are initial operating thresholds, not scientific constants.

- `PROCEED`: AISearchArab preference >= 60% and task success >= 80%, after the measurement-validity gate is satisfied.
- `MODIFY/NARROW`: preference 40–59% or task success 60–79%.
- `PIVOT`: preference < 40% after one focused remediation cycle.
- `INSUFFICIENT_EVIDENCE`: minimum comparison/evaluator/task coverage is not met.

Confidence intervals are reported alongside point estimates. If an interval materially overlaps a decision boundary, the review must record the uncertainty rather than presenting the threshold result as settled.

No feature should be built merely to influence the benchmark unless failure analysis shows that feature directly addresses the failed job.

## Validation Experiment B — Arabic Retrieval & Citation Stress Test

### Hypothesis

The corpus and retrieval layer can answer a broad enough set of real Arabic research queries with high citation correctness and low zero-result rates.

### Phase 1

- 100 human-reviewed Arabic queries.
- Expand toward 500 only after the first error analysis.

### Query families

- model/provider facts;
- AI product/tool facts;
- research and policy questions;
- company/entity questions;
- Arabic/English mixed terminology;
- spelling/transliteration variants;
- freshness-sensitive questions;
- comparison/retrieval tasks.

### Metrics

- Search Success Rate.
- Zero-result Rate.
- Recall@5 and Recall@10 when relevance judgments exist.
- Precision@5.
- MRR@10.
- NDCG@10.
- Citation Accuracy.
- Citation Completeness.
- Groundedness.
- Useful Answer Rate.
- P95 retrieval latency.

### Proposed decision thresholds

- Zero-result <= 10% target; >25% is a serious corpus/retrieval warning.
- Citation Accuracy >= 98% target; below 95% blocks trust claims.
- Groundedness >= 95% target; below 90% after remediation triggers architecture/corpus review.
- Useful Answer Rate >= 80% target; below 60% is a major product-value warning.

Developer-created fixtures are regression assets, not substitutes for this human-reviewed benchmark.

## Validation Experiment C — Demand & Willingness-to-Pay Concierge Test

### Hypothesis

A narrow professional segment values the workflow enough to request continued access, repeat usage, or a paid pilot before a full billing/product expansion is built.

### Sample

- 10–20 qualified users or institutions from the initial ICP.

### Method

Offer a clearly bounded research-intelligence workflow. Manual/concierge fulfillment is permitted where automation is incomplete, provided the participant is told what is automated and what is manual.

Do not collect payment for capabilities that cannot be fulfilled as described.

### Metrics

- repeat usage;
- request for continued access;
- serious pilot interest;
- willingness to pay;
- buyer/decision-maker identity;
- budget/timing constraints;
- reason for refusal.

### Proposed decision thresholds

- >= 30% request continued use: positive demand signal.
- >= 20% show credible paid-pilot intent: strong signal worth deeper validation.
- 0/10 qualified prospects showing credible pilot interest: review ICP/value proposition before monetization engineering.

## Search vs Generated Answer separation

The validation must distinguish two products:

1. `Retrieval/Evidence Product`: search, corpus, entities, provenance, citations.
2. `Generated Answer Layer`: model-synthesized response over reviewed evidence.

Every study should record the AIS mode and whether generated synthesis improved the outcome over retrieval/evidence alone.

Key test:

> If generated answers are disabled, is AISearchArab still worth using?

A strong `yes` is evidence that product value lives in owned information architecture rather than only in a model wrapper.

A generated-answer win must not overwrite retrieval diagnostics. If generated answers score well while retrieval success, citation accuracy, or groundedness are weak, the review must classify the underlying evidence layer as a separate failure mode.

## False-progress controls

The following are not product-validation evidence by themselves:

- commits;
- pull requests;
- number of tests;
- CI success;
- number of agents/tools/APIs;
- number of pages/features;
- design polish;
- architecture complexity.

They may be useful engineering evidence, but the validation gate is decided by user behavior and benchmark outcomes.

## Stop / pivot signals

After two focused validation/remediation cycles, escalate to a pivot/stop review if several of these remain true:

- Blind Preference < 40%.
- Task Success < 60%.
- Week-2 retention < 15%.
- Citation Accuracy cannot remain >= 95%.
- Groundedness remains < 90%.
- No single ICP shows combined usage, retention, and willingness to pay.
- 0/10 qualified institutional prospects show credible pilot intent.
- Cost per successful task makes plausible gross margins structurally negative.
- Users consistently report that the same job is easier in a general-purpose alternative.

Infrastructure defects alone are not product stop signals; they are engineering remediation items unless they make the product economically or operationally infeasible.

## This-week gate

The next high-value evidence is not a new feature. It is a small blind benchmark using real research questions from the target ICP.

Minimum first batch:

- 10 users;
- at least 10 distinct tasks overall;
- at least 30 comparisons;
- record preference, task success, retrieval success, zero-result behavior, citations, groundedness, trust, completion time, mode, query source, and reason.

Treat this as a pilot of the measurement system. Do not claim product-market fit from the first batch.

## Review outcome vocabulary

Every validation review ends with exactly one primary decision:

- `PROCEED`
- `MODIFY`
- `NARROW`
- `PIVOT`
- `STOP`
- `INSUFFICIENT_EVIDENCE`

And must state the cheapest next assumption to test.
