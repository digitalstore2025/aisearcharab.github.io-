# Open-Source-First Build

This project keeps the critical path deployable without proprietary AI infrastructure.

## Current foundation

| Layer | Open-source component | Role |
|---|---|---|
| Web | Hugo | Static multilingual/public site |
| API | FastAPI | Governed application/API layer |
| ORM/migrations | SQLAlchemy + Alembic | Persistence and schema governance |
| Database | PostgreSQL | Transactional/search/evidence store |
| Local AI runtime | Ollama | Optional self-hosted model inference |
| Open-weight reasoning | OpenAI gpt-oss via Ollama | Optional constrained local reasoning profile |
| Containers | Docker Compose compatible configuration | Local/self-hosted orchestration |
| CI | GitHub Actions workflows | Tests, security regression, migrations, evidence |

## Ollama integration

The API contains a standard-library-only `OllamaProvider` adapter at:

`platform/apps/api/src/aisearcharab_api/geo/providers/ollama.py`

Security properties:

- no user-controlled provider URL;
- default network allowlist is limited to `ollama`, `localhost`, and `127.0.0.1`;
- credentials embedded in provider URLs are rejected;
- response size is bounded;
- timeout is bounded;
- malformed/non-JSON responses fail closed;
- citations and mentions are never fabricated by the local model adapter;
- the raw upstream response is preserved for evidence hashing by the existing evidence store.

The adapter uses Ollama's local `/api/chat` endpoint with `stream=false`.

Example application-side construction:

```python
from aisearcharab_api.geo.providers.ollama import OllamaProvider

provider = OllamaProvider(
    model="YOUR_REVIEWED_OPEN_MODEL",
    base_url="http://ollama:11434",
)
result = provider.run_query("ما أفضل مصادر تعلم الذكاء الاصطناعي بالعربية؟", locale="ar")
```

The generic adapter deliberately does not hard-code a model because licensing, language quality, memory requirements, and safety characteristics must be reviewed independently of the runtime.

## OpenAI gpt-oss profile

For the OpenAI open-weight models, use the constrained adapter:

`platform/apps/api/src/aisearcharab_api/geo/providers/gpt_oss.py`

It accepts only the official Ollama model identifiers:

- `gpt-oss:20b` — default local profile;
- `gpt-oss:120b` — high-memory profile.

The default remains `gpt-oss:20b` because OpenAI's Ollama guidance positions it for consumer/local hardware with roughly 16 GB of VRAM or unified memory. The 120B profile requires substantially more memory and should be treated as dedicated-workstation/server class. These hardware figures are planning guidance, not a deployment SLO.

Example:

```python
from aisearcharab_api.geo.providers.gpt_oss import GptOssOllamaProvider

provider = GptOssOllamaProvider()
result = provider.run_query(
    "ما الجهات الأكثر ظهوراً في الإجابات العربية عن الذكاء الاصطناعي؟",
    locale="ar",
)
```

The gpt-oss adapter inherits the hardened Ollama transport: host/port allowlists, redirect rejection, bounded timeout and response size, locale validation, raw-response preservation, and no fabricated citation/mention evidence.

Important product boundary: gpt-oss is text-only and OpenAI reports that its training data is mostly English. AISearchArab must therefore benchmark Arabic quality, hallucination rate, entity fidelity, and citation behavior on its own Arabic evaluation set before treating the model as a production-quality Arabic evaluator.

## Optional local runtime

Run the core stack plus Ollama:

```bash
cd platform
export POSTGRES_PASSWORD='replace-with-a-local-secret'
docker compose -f compose.yaml -f compose.opensource.yaml --profile opensource-ai up -d
```

The Ollama port is bound to loopback only (`127.0.0.1:11434`) rather than all host interfaces.

Pull the default gpt-oss profile explicitly:

```bash
docker compose -f compose.yaml -f compose.opensource.yaml --profile opensource-ai exec ollama ollama pull gpt-oss:20b
```

For the high-memory model:

```bash
docker compose -f compose.yaml -f compose.opensource.yaml --profile opensource-ai exec ollama ollama pull gpt-oss:120b
```

For any other local model, keep the existing reviewed-model workflow:

```bash
docker compose -f compose.yaml -f compose.opensource.yaml --profile opensource-ai exec ollama ollama pull YOUR_REVIEWED_OPEN_MODEL
```

## Production boundary

`compose.opensource.yaml` is a development/self-hosted foundation, not a production-release claim. Before production use:

1. pin every external container image by immutable digest;
2. review the selected model license, usage policy, and redistribution terms;
3. benchmark Arabic quality, hallucination rate, latency, memory, throughput, and adversarial robustness;
4. keep Ollama inaccessible from the public network;
5. implement secrets management outside `.env` for production;
6. add observability, resource limits, backups/PITR, and incident controls;
7. generate release evidence for the exact deployment SHA and image digests;
8. keep generated reasoning output separate from independently verified evidence and citations.

## Next open-source milestones

The next highest-value integrations should remain modular rather than mandatory:

- Arabic gpt-oss evaluation fixtures and reproducible benchmark reports;
- OpenTelemetry for traces/metrics;
- Prometheus + Grafana for self-hosted observability;
- MinIO or another S3-compatible store for immutable evidence objects when database-only storage becomes insufficient;
- optional pgvector when semantic retrieval is justified by measured recall gains;
- a controlled open-source crawler/search ingestion service behind the existing SSRF boundary.

Do not add an infrastructure component until a measured product requirement justifies its operational and security cost.
