# Implementation status — v2

## Implemented
- Policy Gateway: allow / approval / deny + default deny.
- MCP preflight gateway with trust labels and prompt-injection blocking.
- Skill Registry and deterministic minimal router.
- Model/cost tier router with independent-verifier tier.
- JSONL observability tracer.
- Memory namespaces and verified/fresh fact gate.
- RAG dedupe/hybrid scoring/citation metric primitive.
- Definition-of-Done engines for code and research.
- Research provenance/contradiction graph primitives.
- Red-team finding schema with evidence requirement.
- Independent verifier interface.
- A/B evaluation metrics and promotion/rejection rule.
- Failure clustering for eval-driven improvement.
- Artifact hash/provenance records.
- Project profiles.
- CI workflow and static eval suites.

## Integration boundaries intentionally left external
- Actual cloud IAM/network/sandbox enforcement.
- Real MCP server execution adapters.
- Durable database/vector store.
- Vendor-specific model IDs and prices.
- Production telemetry backend.
- Human approval UI.

These are environment-specific. The core package exposes the control points required to integrate them without weakening policy.
