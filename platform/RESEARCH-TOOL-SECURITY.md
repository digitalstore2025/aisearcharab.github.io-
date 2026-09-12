# Research and Agent Tool Security

Status: server-side tool policy, research-source preflight, and a pinned-IP HTTP(S) transport are implemented. No generic model-accessible fetcher, crawler, browser, MCP action surface, shell tool, autonomous publisher, payment action, or public research endpoint is enabled.

## Threat model

A model is an untrusted planner. Prompt injection, poisoned evidence, malicious webpages, user-controlled instructions, or hallucination must never create a new tool, expand permissions, choose an arbitrary network destination, disable approval, or alter retry/idempotency policy.

## Tool capability boundary

`tool_policy.py` provides a server-owned registry. Every future model-callable tool declares a stable name, application permissions, replay class, approval requirement, allowed research sources, and idempotency-key policy. Authorization uses application-derived context; the LLM cannot grant itself permissions, approval, tenant scope, network scope, or idempotency guarantees.

Non-idempotent side effects require approval. Idempotent side effects require a persistent idempotency key. Network-capable and side-effecting tools require explicit application permissions.

## Research network preflight

`research_policy.py` enforces explicit source IDs and host allowlists, subdomains opt-in, HTTP/HTTPS and ports 80/443, credential rejection, public-IP DNS checks, private/link-local/metadata/CGNAT rejection, bounded redirects, response-size/time ceilings, and connected-peer verification.

Unregistered source IDs and unallowlisted hosts are rejected before DNS resolution.

## Pinned transport

`research_fetcher.py` implements the transport required to close the DNS-rebinding/TOCTOU gap. It:

- opens TCP only to IP addresses produced by the approved preflight;
- preserves the original DNS hostname for TLS SNI, certificate verification, and HTTP `Host`;
- checks the connected peer against the preflight address set;
- disables automatic redirect handling and sends every redirect back through the source policy;
- bounds URL length, DNS address fan-out, redirects, headers, response bytes, and timeouts;
- requests identity encoding and rejects compressed content until a bounded decompression policy exists;
- rejects duplicate `Content-Length`, ambiguous `Content-Length` plus `Transfer-Encoding`, unsupported transfer framing, and unsupported/missing content types;
- sends only fixed research headers and does not forward authorization, cookies, internal headers, or browser state;
- closes the response and connection for every hop;
- returns a SHA-256 body digest for downstream provenance/integrity recording;
- emits payload-free timing telemetry only.

The transport remains an internal primitive. No source is activated for arbitrary model use merely because the transport exists.

## Prompt-injection boundary

Retrieved text is data, never authority. Research workers must not execute commands, follow embedded tool instructions, reveal secrets, or widen source scope based on webpage text. External claims require provenance and server-side citation/evidence controls before they become grounded claims.

Before model consumption, a separate parser/sanitizer boundary must convert accepted HTML/XML/JSON/text into bounded, provenance-carrying evidence. Raw fetched markup must not be injected directly into a privileged system or tool prompt.

## MCP boundary

MCP is a transport, not a permission model. Any future MCP tool must map into `ToolCapabilityRegistry` and pass the same permissions, validation, idempotency, source policy, and approval controls.

## Observability boundary

Tool/research execution uses payload-free observability. Routine telemetry may include validated workflow/tool IDs, request ID, duration and bounded outcome/failure class. It must not record raw queries, URLs/query strings, response bodies, prompts, tool arguments, credentials, cookies, evidence text, or model output.

## Remaining activation gate

External research remains disabled for model-controlled production use until all of the following are complete:

1. source registry configuration is reviewed and remains outside model/user control;
2. a bounded parser/sanitizer strips active content and produces provenance-carrying evidence records;
3. prompt-injection and poisoned-source evaluations pass;
4. per-user/tenant rate, concurrency, byte and cost budgets exist;
5. privacy and retention rules cover fetched content and derived evidence;
6. Staging demonstrates latency, failure behavior and rollback/kill-switch operation;
7. evidence/citation postconditions remain fail-closed across external-research paths.
