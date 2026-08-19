# GPT-OSS Arabic Benchmark Protocol

AISearchArab uses this benchmark to decide whether a local `gpt-oss` profile is good enough for Arabic grounded evaluation work. The benchmark is evidence-oriented: it does not treat a model name, successful HTTP call, or fluent Arabic as proof of quality.

## What is measured

The v1 suite is synthetic and versioned so model changes can be compared against exactly the same evidence. It covers:

- grounded fact recovery from Arabic context;
- Arabic response compliance;
- entity fidelity and disambiguation;
- negation and scope control;
- simple arithmetic and ordering;
- correction/recency reasoning inside a supplied context;
- explicit abstention when the answer is absent;
- unsupported URL/citation detection;
- forbidden-claim detection;
- p50 and p95 end-to-end provider latency.

The suite intentionally avoids mutable world-knowledge questions. Those mix model quality with training-date and freshness effects and therefore make regression evidence less reproducible.

## Dataset

The canonical fixture is:

`platform/apps/api/tests/fixtures/gpt_oss_ar_benchmark.json`

Every case contains a fixed Arabic context, a question, a golden reference answer, required term groups, optional required entities, forbidden claims, and case-level policy such as mandatory abstention or URL allowance.

The runner hashes the exact dataset bytes with SHA-256 and records that digest in every report.

## Transparent gates

The default v1 promotion gates are:

| Metric | Gate |
|---|---:|
| Mean score | `>= 0.80` |
| Case pass rate | `>= 0.80` |
| Arabic locale rate | `>= 0.90` |
| Grounded term recall | `>= 0.80` |
| Entity recall | `>= 0.90` |
| Unsupported URL rate | `== 0` |
| Forbidden claim rate | `== 0` |
| Abstention accuracy | `>= 0.80` |

Latency is reported as p50/p95 but is not a universal gate in v1 because acceptable latency depends on the deployment hardware. A production deployment must define its own latency SLO on the exact target GPU/CPU configuration.

## Validate the benchmark without a model

This validates the schema and verifies that the golden reference answers satisfy the scoring gates:

```bash
cd platform/apps/api
python scripts/benchmark_gpt_oss_ar.py --validate-only
```

This is what GitHub CI runs. It does **not** claim to benchmark the model.

## Run the real 20B benchmark

Start the optional Ollama profile and pull the model first:

```bash
cd platform
export POSTGRES_PASSWORD='replace-with-a-local-secret'
docker compose -f compose.yaml -f compose.opensource.yaml --profile opensource-ai up -d ollama
docker compose -f compose.yaml -f compose.opensource.yaml --profile opensource-ai exec ollama ollama pull gpt-oss:20b
```

Then run from the API directory on the host. The Ollama compose profile binds to loopback, so the default safe host target is `localhost:11434`:

```bash
cd platform/apps/api
python scripts/benchmark_gpt_oss_ar.py \
  --model gpt-oss:20b \
  --base-url http://localhost:11434 \
  --output ../../artifacts/gpt-oss-20b-ar.json \
  --include-answers \
  --enforce-gates
```

Exit codes:

- `0`: run completed; when `--enforce-gates` is set, all gates passed;
- `1`: run completed but one or more quality gates failed;
- `2`: Ollama/model transport failed before a complete report could be produced.

## Compare 20B and 120B

Run the exact same dataset separately for each model and preserve both reports:

```bash
python scripts/benchmark_gpt_oss_ar.py \
  --model gpt-oss:120b \
  --base-url http://localhost:11434 \
  --output ../../artifacts/gpt-oss-120b-ar.json \
  --include-answers \
  --enforce-gates
```

Do not compare latency across different hardware as though it were a model-only effect. Record the GPU/CPU, memory, Ollama version, model digest and runtime configuration alongside the JSON report when producing release evidence.

## Evidence retained

A live report contains:

- benchmark/schema version;
- UTC timestamp;
- dataset SHA-256;
- provider and exact model identifier;
- aggregate quality metrics;
- gate thresholds and failures;
- per-case metrics;
- end-to-end latency;
- SHA-256 of each raw Ollama response;
- answer text only when `--include-answers` is explicitly enabled.

The raw response itself is not duplicated into the benchmark report by default. The existing provider/evidence path remains responsible for preserving upstream evidence where required.

## Interpretation boundary

Passing this suite means the model cleared the **v1 grounded-Arabic benchmark on the tested runtime**. It does not prove general Arabic excellence, current factual knowledge, safety against all prompt attacks, or production readiness.

Before promotion to a production evaluator, also require:

1. a larger real AISearchArab corpus with blind human review;
2. prompt-injection and adversarial Arabic cases;
3. repeated runs to quantify variance;
4. target-hardware throughput and latency SLOs;
5. model/runtime digest pinning;
6. release evidence tied to the exact application commit and deployment configuration.

The v1 scorer is intentionally transparent and deterministic. Its phrase/entity checks are auditable but coarse; future semantic or human judging should supplement this baseline rather than silently replace it.
