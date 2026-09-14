# AI Search release gate

This document defines the minimum release evidence for AI Search Arab before any public claim of production readiness.

## Discovery and machine-readable surfaces

Required on the canonical origin:

- `/robots.txt`
- `/sitemap.xml`
- `/index.xml`
- `/index.json`
- `/llms.txt`
- `/ai-search-readiness.json`
- canonical links on public HTML pages
- JSON-LD appropriate to the page type
- `rel="describedby"` discovery for `/llms.txt`

## Evidence ladder

The following states are deliberately non-equivalent:

1. Implementation: code exists in the repository.
2. CI: exact-head automated checks pass.
3. Merge: reviewed code is integrated into the target branch.
4. Deployment: an artifact was published to an environment.
5. Runtime verification: the deployed origin was probed and observed behaving as intended.
6. Production readiness: governance, security, operational, performance, recovery, and human approval gates are satisfied together.

No lower state may be relabeled as a higher state.

## AI Search / GEO quality rules

- Prefer original, non-commodity Arabic reporting and analysis.
- Publish explicit sources, dates, methodology, corrections, and stable canonical URLs.
- Use structured data only for facts visible on the page.
- Never fabricate reviews, ratings, authorship, organizations, citations, or external identities for search visibility.
- Keep content crawlable unless a documented safety/privacy reason requires exclusion.
- Treat `llms.txt` as an auxiliary agent-discovery surface, not a replacement for canonical SEO, robots, sitemaps, structured data, or Search Console/Webmaster verification.
- IndexNow is optional and requires real domain ownership/key evidence before activation.

## Operational blockers that remain external

Repository code cannot prove or configure every external control. Production claims remain blocked until live evidence establishes, at minimum:

- enforced branch protection or equivalent repository ruleset;
- exact-head required checks and review policy;
- staging deployment and external runtime probe success;
- production deployment and rollback evidence;
- secrets/IAM/network controls;
- backup/restore evidence for persistent data;
- observability and incident response evidence;
- security and accessibility review;
- real-user Arabic search/retrieval evaluation and load evidence.
