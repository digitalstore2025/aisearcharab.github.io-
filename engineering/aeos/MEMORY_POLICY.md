# AEOS Memory Policy

## Durable memory may contain

- accepted architecture and ADR decisions;
- stable schemas and public contracts;
- security and privacy decisions;
- deployment facts verified from the environment;
- recurring failure modes and their verified fixes;
- unresolved risks and explicit constraints;
- editorial/source-provenance rules that materially affect implementation.

## Durable memory must not contain

- secrets, credentials, tokens, private keys, or session material;
- identities or raw evidence for protected human sources;
- unpublished sensitive investigative material;
- raw chain-of-thought or hidden reasoning;
- transient speculation presented as fact;
- obsolete implementation details contradicted by the repository.

## Retrieval discipline
Load only the memory relevant to the current decision. Repository files and current execution evidence outrank stale remembered context.

## Update rule
A memory item is durable only after the associated decision or fact is verified and has a clear source in the repository, deployment evidence, or approved project record.
