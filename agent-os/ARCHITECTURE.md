# Astra Agent OS v2 architecture

```text
User Task
   │
   ▼
Task Contract ──► Profile
   │
   ├──► Skill Registry / Router
   ├──► Model & Cost Router
   ├──► Agent Registry / Team Planner
   └──► Definition of Done
                │
                ▼
       Execution Coordinator
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
  Plan agents  Build waves  Release prep
     │          │          │
     └──────────┴────┬─────┘
                     ▼
              Tool Router
                     │
          ┌──────────┴─────────┐
          ▼                    ▼
 Prompt-Injection         Policy Gateway
 Inspection               (default deny)
          │                    │
          └──────────┬─────────┘
                     ▼
                  MCP/Tools
                     │
                     ▼
             QA + Security Verify
                     │
                     ▼
             Independent Reviewer
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
5. Multi-agent work is bounded: broad projects use staged waves; narrow tasks do not summon the full team.
6. Agent tool declarations are intersected with the active project profile and never bypass runtime policy.
7. High-risk work requires adversarial security verification plus independent completion review.
8. Memory items are not treated as facts unless provenance/freshness permit it.
9. Prompt, skill, and agent-routing changes are software changes: test them before promotion.
