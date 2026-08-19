# Open-source runtime profile

The optional self-hosted AI runtime is defined in `compose.opensource.yaml`.

Core rules:

- proprietary AI services are not required for the local critical path;
- Ollama is optional and isolated from the public network by loopback port binding;
- the generic API adapter is `aisearcharab_api.geo.providers.ollama.OllamaProvider`;
- the constrained OpenAI open-weight adapter is `aisearcharab_api.geo.providers.gpt_oss.GptOssOllamaProvider`;
- the gpt-oss adapter accepts only the official Ollama identifiers `gpt-oss:20b` and `gpt-oss:120b`, defaulting to `gpt-oss:20b`;
- the provider endpoint is allowlisted and configuration-controlled;
- local models must not fabricate citations or mentions;
- arbitrary local models remain deliberately opt-in through the generic Ollama adapter: license, Arabic quality, memory, latency, and safety must be reviewed per deployment;
- production deployments must pin the Ollama container by immutable digest and re-run release evidence.

Full design, gpt-oss usage, and production boundaries: `../docs/OPEN_SOURCE_BUILD.md`.
