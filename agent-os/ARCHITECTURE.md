# Astra Agent OS v2 architecture

```text
User Task
   │
   ▼
Task Contract ──► Profile
   │
   ├──► Skill Registry / Router
   ├──► Model & Cost Router
   └──► Definition of Done
                │
                ▼
          Agent / Model
                │
                ▼
           Tool Router
                │
      ┌─────────┴─────────┐
      ▼                   ▼
Prompt-Injection      Policy Gateway
Inspection            (default deny)
      │                   │
      └─────────┬─────────┘
                ▼
             MCP/Tools
                │
                ▼
        Verification / Repair
                │
                ▼
        Provenance + Artifacts
                │
                ▼
        Definition of Done

All stages ──► Observability traces ──► Failure clustering ──► New evals
```

## Design invariants
1. Policy enforcement lives outside model text.
2. Untrusted retrieved content never grants privileges.
3. Minimal context beats unconditional context loading.
4. Model choice is proportional to task complexity and risk.
5. High-risk work requires independent verification, not only stronger generation.
6. Memory items are not treated as facts unless provenance/freshness permit it.
7. Prompt and skill changes are software changes: test them before promotion.
