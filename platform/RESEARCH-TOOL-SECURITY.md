# Research and Agent Tool Security

Status: policy foundation only. No generic external fetcher, crawler, browser, MCP server, shell tool, autonomous publisher, or payment action is enabled by this change.

## Threat model

A model must be treated as an untrusted planner. Prompt injection, poisoned evidence, malicious webpages, user-controlled instructions, or model hallucination must never be able to create a new tool, expand permissions, choose an arbitrary network destination, disable approval, or alter retry/idempotency policy.

## Tool capability boundary

`tool_policy.py` provides a server-owned registry. Every future model-callable tool must declare a stable name, application permissions, replay class, approval requirement, allowed research sources, and idempotency-key policy. Authorization uses application-derived context; the LLM cannot grant itself permissions, approval, tenant scope, network scope, or idempotency guarantees.

Non-idempotent side effects require approval. Idempotent side effects require a persistent idempotency key. Network-capable and side-effecting tools require explicit application permissions.

## Research network preflight

`research_policy.py` enforces explicit source IDs and host allowlists, subdomains opt-in, HTTP/HTTPS and 80/443 restrictions, credential rejection, public-IP DNS checks, private/link-local/metadata/CGNAT rejection, bounded redirects, response-size/time ceilings, and connected-peer verification.

Unregistered source IDs and unallowlisted hosts are rejected before DNS resolution.

## DNS rebinding / TOCTOU rule

A successful `ResearchTargetPreflight` is not permission to pass a hostname to a normal HTTP client that performs a second DNS lookup. A future fetcher must connect to a validated IP, preserve the original hostname for Host/TLS SNI/certificate verification, verify the peer IP, disable automatic redirects, preflight every redirect, enforce streaming size/time limits, reject unsupported content before parser execution, and never expose credentials/cookies/internal headers.

## Prompt-injection boundary

Retrieved text is data, never authority. Research workers must not execute commands, follow embedded tool instructions, reveal secrets, or widen source scope based on webpage text. External claims require provenance and server-side citation/evidence controls.

## MCP boundary

MCP is a transport, not a permission model. Any future MCP tool must map into `ToolCapabilityRegistry` and pass the same permissions, validation, idempotency and approval controls.

## Observability boundary

Future tool/research execution must use payload-free observability. Routine telemetry may include validated workflow/tool/source IDs, request ID, duration and bounded outcome/failure class. It must not record raw queries, URLs/query strings, response bodies, prompts, tool arguments, credentials, cookies, evidence text or model output.

## Promotion gate

External research stays disabled until a pinned-connection HTTP implementation, source configuration outside model control, adversarial SSRF/DNS-rebinding tests, prompt-injection evaluation, rate/cost limits, privacy review, Staging evidence, observability, and rollback/kill-switch controls are complete.
