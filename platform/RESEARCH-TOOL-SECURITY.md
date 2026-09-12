# Research and Agent Tool Security

Status: policy foundation only. No generic external fetcher, crawler, browser, MCP server, shell tool, autonomous publisher, or payment action is enabled by this change.

## Threat model

A model must be treated as an untrusted planner. Prompt injection, poisoned evidence, malicious webpages, user-controlled instructions, or model hallucination must never be able to create a new tool, expand permissions, choose an arbitrary network destination, disable approval, or alter retry/idempotency policy.

## Tool capability boundary

`tool_policy.py` provides a server-owned registry. Every future model-callable tool must declare:

- a stable tool name;
- required application permissions;
- a replay class;
- whether human approval is required;
- the exact research-source identifiers it may access;
- whether an idempotency key is mandatory.

Authorization uses application-derived context. The LLM may request a registered tool name and arguments, but it does not supply or grant its own permissions, approval state, tenant boundary, idempotency guarantees, or network allowlist.

Non-idempotent side-effect registrations are rejected unless they require approval. Idempotent side-effect registrations are rejected unless they require an invocation idempotency key. These declarations still do not make a destination idempotent automatically; the implementation must prove enforcement at the persistence/API boundary before retries are enabled.

## Research network preflight

`research_policy.py` adds per-source network policy with:

- explicit source IDs;
- exact host allowlists, with subdomains opt-in rather than default;
- explicit HTTP/HTTPS scheme and port policy;
- URL-credential rejection inherited from the shared network validator;
- public-IP DNS resolution checks;
- localhost/private/link-local/metadata/CGNAT rejection;
- bounded redirect count;
- response-size and timeout ceilings carried in the preflight result;
- connected-peer verification against the preflight DNS address set.

Unregistered source IDs and unallowlisted hosts are rejected before DNS resolution.

## DNS rebinding / TOCTOU rule

A successful `ResearchTargetPreflight` is **not** permission to pass the hostname to a normal HTTP client that performs a new DNS resolution. That would reopen DNS-rebinding/TOCTOU risk.

A future generic fetcher must:

1. obtain a preflight result;
2. connect to one of the already validated public IP addresses;
3. preserve the original hostname for HTTP `Host` and TLS SNI/certificate verification;
4. verify the connected peer IP with `validate_connected_peer`;
5. disable automatic redirects and preflight every redirect hop separately;
6. enforce the source timeout and response-size ceiling while streaming;
7. reject unsupported content/encoding before parser execution;
8. never expose credentials, internal headers, cookies, session state, or cloud metadata to external sources.

Until that pinned-connection fetcher exists and is independently reviewed, generic web research remains blocked.

## Prompt-injection boundary

Retrieved text is data, never authority. Future research workers must keep system/tool policy outside retrieved content and must not execute commands, follow embedded tool instructions, reveal secrets, or widen source scope based on webpage text. Claims derived from external material must carry provenance and pass the same server-side evidence/citation controls before being presented as grounded facts.

## MCP boundary

MCP is an integration transport, not a permission model. A future MCP connector must map every exposed MCP tool into the same `ToolCapabilityRegistry`; connector-provided tool names do not become executable merely because the server advertises them. High-impact MCP actions require explicit application permission, argument validation, idempotency policy, and approval where applicable.

## Observability boundary

Future tool/research execution must use the platform's payload-free observability boundary rather than ad-hoc logs. Routine telemetry may identify a validated workflow/tool/source ID, request ID, duration and bounded outcome/failure class. It must not record raw query text, full URLs or URL query strings, fetched response bodies, prompts, tool arguments, credentials, cookies, evidence text or model output. Any OpenTelemetry exporter must preserve the same attribute allowlist rather than serializing application payloads into spans.

## Promotion gate

External research remains disabled until the project has a pinned-connection HTTP implementation, source registry configuration outside model control, adversarial SSRF/DNS-rebinding tests, prompt-injection evaluation, rate/cost limits, privacy review, Staging evidence, observability, and rollback/kill-switch controls.
