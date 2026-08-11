# AISearcharab — Product Audit

## Product objective

مرصد الذكاء الاصطناعي العربي: public Arabic-first observatory with governed editorial workflows and retrieval/search. The current release does not claim generated AI answers, RAG, crawling or payments.

## UX / accessibility findings

| Dimension | Evidence | Status |
|---|---|---|
| Empty states | Public/admin interfaces contain explicit empty-result/content/source/claim states | IMPLEMENTED |
| Loading states | Search/admin flows expose status messages while data is loading | IMPLEMENTED |
| Error states | API failures are surfaced through status/alert text rather than silent failure | IMPLEMENTED |
| Keyboard | Admin forms/buttons/dialog use native controls; step-up dialog handles cancel/focus | IMPLEMENTED_CODE; MANUAL_VERIFY_PENDING |
| ARIA | Status/alert and dialog labelling exist in privileged UI | IMPLEMENTED_CODE; MANUAL_VERIFY_PENDING |
| RTL | Hugo public surface is Arabic RTL-first and admin copy/layout is Arabic-oriented | IMPLEMENTED_CODE; BROWSER_VERIFY_PENDING |
| Contrast | CSS was previously hardened, but no independent WCAG 2.2 AA measurement is attached to this branch | EXTERNAL_VERIFY_PENDING |
| XSS-safe rendering | Admin dynamic values are inserted through `textContent`/created DOM nodes; CI rejects executable HTML sinks | PENDING_CI |
| Autosave | Not enabled intentionally: governed editorial changes must be explicit, auditable mutations rather than hidden background writes | INTENTIONAL_NON_FEATURE |
| Undo | Workflow supports explicit state transitions and review invalidation; generic client-side undo is not used because it would conflict with audited server state | INTENTIONAL_NON_FEATURE |
| Weak devices | Static Hugo front-end has no framework hydration/runtime bundle; asset-size budgets already exist | IMPLEMENTED |
| Virtualization | Not required for current bounded admin/public result sets; large unbounded client lists are not exposed | N/A CURRENT_SCALE |
| Lighthouse | No live-browser Lighthouse run is available in repository evidence | NOT_CLAIMED |

## Acceptance thresholds

The target `Performance >=85 / Accessibility >=95 / Best Practices >=95 / SEO >=90` remains an external browser measurement. It is not marked achieved until a real HTTPS deployment is audited. Static build budgets and semantic checks are supporting evidence, not Lighthouse substitutes.

## Product hardening in this branch

- response CSP hardened without enabling inline/eval execution;
- privileged JS dangerous-sink regression added;
- streamed request size failures return a deterministic 413 instead of reaching parsers/routes;
- malicious requests to a nonexistent upload surface remain nonexistent rather than creating a hidden storage feature;
- a newly created editor is tested through an allowed draft-creation path and a denied owner-account mutation path.

## Release UX gate

Before promotion to `EXTERNALLY_VERIFIED`, capture browser evidence for mobile widths, desktop, RTL, keyboard-only navigation, focus visibility, screen reader landmarks/forms, contrast and actual Lighthouse scores. No code-level report substitutes for that evidence.
