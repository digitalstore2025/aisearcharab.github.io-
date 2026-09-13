# Multi-Agent Team Architecture

Agent OS uses a bounded team rather than an unconstrained swarm.

## Team
- `execution-coordinator`: decomposition, dependencies, decisions, Definition of Done.
- `product-strategy`: product scope and acceptance criteria.
- `software-architect`: architecture and interfaces.
- `backend-platform`: APIs, persistence and integrations.
- `frontend-accessibility`: Arabic/RTL UI, WCAG and web performance.
- `ai-rag`: retrieval, grounding, prompts/model routing.
- `data-evals`: datasets, metrics and regression evaluation.
- `research-osint`: source verification, claims and provenance.
- `seo-geo`: crawlability, structured data and answer-engine visibility.
- `devops-release`: CI/CD, staging, observability and rollback.
- `qa-reliability`: test strategy and reproducible failure evidence.
- `security-redteam`: adversarial security verification.
- `independent-reviewer`: final evidence and completion challenge.

## Execution model
1. Coordinator creates the scoped task contract.
2. Planning agents resolve product/architecture dependencies.
3. Build agents run in bounded waves; default maximum wave size is four.
4. Release-preparation work is produced before final verification.
5. QA and security verify independently.
6. The independent reviewer receives evidence and open risks from every selected worker and may reject completion.

A project-wide task activates portfolio mode. A narrow task activates only agents whose triggers match, plus QA and the independent reviewer. High-risk work also mandates the security agent.

Agent-level tool declarations are not capabilities by themselves: the active project profile intersects them, and every external/state-changing action still passes the runtime policy gateway.
