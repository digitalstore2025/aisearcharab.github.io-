# FreeLLMAPI as a private inference gateway

## Decision

Use FreeLLMAPI only as an internal OpenAI-compatible routing/failover service for the existing AISearcharab API. Do not turn it into the platform's identity, authorization, quota, billing, or tenant boundary.

The public Hugo site remains static-first. The existing FastAPI service remains the only application API and the authority for user authentication, CSRF, RBAC, per-user request quotas, evidence retrieval, answer validation, and audit records.

## Existing integration point

The optional integration is limited to the existing grounded-answer workflow:

```text
Browser / static site
  -> AISearcharab FastAPI (/v1/answers/grounded)
     -> authenticate + authorize + CSRF
     -> retrieve published/indexed content and reviewed claims
     -> reserve per-user quota and audit request
     -> OpenAI SDK Responses API
        -> private FreeLLMAPI (/v1/responses)
           -> configured upstream model/provider
     -> validate structured output and selected claim identifiers
     -> revalidate claim revision/status in the database
     -> render exact reviewed claim text and server-owned citations
     -> record usage, latency, outcome and resolved model
```

The model remains a claim selector. It must not author factual prose, citations, or evidence. The server renders the exact reviewed claim text. Provider routing does not weaken this evidence contract.

## Runtime configuration

The API accepts these environment variables:

- `OPENAI_API_KEY`: OpenAI API key or the FreeLLMAPI unified bearer token. Secret only; backend runtime only.
- `OPENAI_BASE_URL`: optional absolute API root ending in `/v1`. Omit it to use the OpenAI SDK default endpoint.
- `OPENAI_ALLOWED_HOSTS`: exact comma-separated host allowlist; required when a gateway URL is configured in staging/production. Wildcards are rejected. Plain HTTP is permitted only for loopback hosts in local development.
- `OPENAI_MODEL`: model alias accepted by the gateway catalog.
- `GENERATED_ANSWERS_ENABLED`: remains false by default.

Example for local development only:

```dotenv
GENERATED_ANSWERS_ENABLED=true
OPENAI_API_KEY=<secret-manager-value>
OPENAI_BASE_URL=http://127.0.0.1:3001/v1
OPENAI_MODEL=<verified-responses-compatible-model>
```

Staging and production configuration must use HTTPS. URL credentials, query strings, fragments, non-`/v1` paths, and malformed ports are rejected during settings validation. Never place a token in the URL.

The Docker Compose API runtime receives the gateway variables. The migration container deliberately does not receive the inference credential.

## Security boundary

FreeLLMAPI is a single-user gateway, not a multi-tenant service. Its unified token is a service credential and must never be exposed to browsers, end users, client-side JavaScript, or tenant records.

Required deployment controls:

1. Place FreeLLMAPI on a private network. Permit inbound traffic only from the FastAPI service.
2. In staging/production, set `OPENAI_ALLOWED_HOSTS` to the exact private DNS hostname used by `OPENAI_BASE_URL`; wildcard entries are rejected. Enforce outbound network policy so the API can reach only the approved gateway and cannot send the shared bearer token or evidence to arbitrary public hosts. The application allowlist is not a substitute for firewall/egress enforcement.
3. The OpenAI SDK transport is configured with redirects disabled, preventing a trusted gateway from redirecting credential-bearing requests to another origin.
4. Plain HTTP is accepted only for loopback addresses (`localhost`, `127.0.0.1`, `::1`) during local development; all non-loopback destinations require HTTPS.
5. Do not publish the gateway port to the public Internet.
6. Keep its dashboard and administrative endpoints private.
7. Disable MCP unless a separate, reviewed use case requires it. MCP shares the gateway credential and exposes capabilities beyond simple inference.
8. Do not mount `/var/run/docker.sock` into the gateway container.
9. Pin a reviewed release and immutable image digest; do not deploy `latest`.
10. Store the unified token in the platform secret manager and rotate it after suspected exposure.
11. Keep user identity, per-user quotas, abuse controls, and audit records in FastAPI/PostgreSQL. The gateway's shared provider quota is not a customer entitlement or a billing ledger.
12. Do not send secrets, source identities, unpublished evidence, or other sensitive material to third-party providers unless the data classification and provider terms explicitly permit it.

## Compatibility and correctness

FreeLLMAPI exposes a Responses API compatibility route and maps Responses structured-output settings into its internal completion format. This makes it a plausible protocol fit for the current SDK call, but it does not establish identical behavior across every upstream model/provider.

The application therefore continues to enforce all of the following locally:

- completed response status;
- valid JSON matching the local Pydantic schema;
- known claim identifiers only;
- no model-authored factual answer text;
- valid model and token-usage provenance;
- evidence revalidation after provider latency;
- server-generated citations and exact claim rendering.

If the gateway or provider omits required usage/model metadata, returns malformed structured output, or cannot complete the request, the application fails closed. Do not weaken these checks to accommodate a provider.

## Provider terms and data governance

The gateway's open-source license applies to the gateway code; it does not grant rights to use, resell, or redistribute upstream model services. Review each provider's commercial-use terms, free-tier restrictions, data retention, logging, geographic processing, and rate limits before enabling it. Do not treat advertised aggregate free-token estimates as guaranteed capacity.

FreeLLMAPI's upstream project documentation describes the project as intended for personal experimentation. Production or commercial use therefore requires a separate provider-by-provider and project-terms review.

## Rollout gates

### Local development

- Configure a local/private gateway endpoint.
- Run the generated-answer unit and API tests.
- Verify the gateway's `/v1/responses` response contains a completed status, resolved model identifier, and valid input/output/total token counts.
- Test malformed JSON, unknown claim IDs, missing usage, timeout, 429, and provider 5xx behavior.
- Confirm no gateway token appears in browser assets, API responses, or logs.

### Staging

- Use a private HTTPS endpoint and a staging-only gateway token.
- Run smoke tests through the actual FastAPI endpoint, not directly from the browser.
- Confirm per-user quota reservations and audit events are written before provider calls.
- Verify no provider receives data outside the approved classification.
- Run latency, concurrency, failover, and cost-observation tests.

### Production

Production activation remains blocked. The current application configuration deliberately rejects `GENERATED_ANSWERS_ENABLED=true` in production until distributed rate limiting and observability are independently verified. This integration change does not remove that gate.

Before reconsidering activation, require:

- verified distributed rate limiting and quota behavior;
- cost and usage reconciliation against gateway/provider evidence;
- independent security review of the deployed gateway and network boundary;
- provider legal/terms review;
- retention and deletion policy approval;
- staging evidence and a tested kill switch;
- independent review of the exact release commit.

## Non-goals

This change does not:

- deploy or provision FreeLLMAPI;
- add public access to the gateway;
- expose the gateway token to users;
- create tenant accounts or tenant keys in FreeLLMAPI;
- enable MCP;
- enable generated answers in production;
- enable payments, subscriptions, or commercial resale;
- claim that all upstream free tiers are stable or contractually available.
