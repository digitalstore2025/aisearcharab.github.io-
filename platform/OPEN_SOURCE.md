# Open-source runtime profile

The optional self-hosted AI runtime is defined in `compose.opensource.yaml`.

Core rules:

- proprietary AI services are not required for the local critical path;
- Ollama is optional and isolated from the public network by loopback port binding;
- the API adapter is `aisearcharab_api.geo.providers.ollama.OllamaProvider`;
- the provider endpoint is allowlisted and configuration-controlled;
- local models must not fabricate citations or mentions;
- the selected model is deliberately not hard-coded: license, Arabic quality, memory, latency, and safety must be reviewed per deployment;
- production deployments must pin the Ollama container by immutable digest and re-run release evidence.

Full design and production boundaries: `../docs/OPEN_SOURCE_BUILD.md`.
