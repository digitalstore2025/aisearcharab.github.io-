# AISearchArab UI PromptOps Pilot — 2026-08-19

Scope: static code audit of the current Hugo frontend and conversion of findings into evidence-gated prompts.

This document does **not** claim live-browser, Lighthouse, visual-regression, or assistive-technology results. Those remain unverified until rendered tests run.

## Evidence inspected

- `layouts/_default/baseof.html`
- `layouts/index.html`
- `layouts/search.html`
- `static/css/main.css`
- `static/css/search.css`
- `README.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`

## Observed strengths

### Architecture

- Static-first Hugo frontend.
- Minimal progressive JavaScript.
- Existing repository rules explicitly prevent claiming success without tests.

### Arabic/RTL

- Root document uses Arabic and RTL.
- CSS uses logical properties in important layout areas.
- LTR technical content is isolated where required.

### Accessibility-oriented implementation

- Skip link exists.
- Main content has a stable target.
- Visible `:focus-visible` treatment exists for links, buttons, fields, selects, textareas, and summaries.
- Search input has a hidden accessible label.
- Search status uses `role="status"` and `aria-live="polite"`.
- Reduced-motion CSS is present.
- Tables become horizontally scrollable at narrow widths.

### Responsive implementation

Existing breakpoints are already present around:

- 1040px;
- 720px;
- 420px;
- search form around 620px.

Therefore new UI prompts should reuse or justify changes to the current breakpoint model rather than create arbitrary parallel breakpoints.

## Evidence-based risks and opportunities

### High — AI-generated redesign regression risk

The current UI already encodes RTL, accessibility, responsive, and Static-First constraints. A generic “modernize/redesign” prompt can easily replace semantic elements, introduce unnecessary JavaScript/frameworks, remove logical properties, or lose focus/reduced-motion behavior.

**Control:** apply the baseline-freeze and atomic-iteration protocol from `docs/UI_PROMPTOPS_SYSTEM.md`.

### Medium — navigation discoverability at narrow widths

At widths below 1040px, the primary navigation becomes horizontally scrollable. This is a valid low-JavaScript strategy, but a future redesign must explicitly verify discoverability, keyboard focus visibility during horizontal scrolling, touch target sizing, and overflow behavior rather than assume “responsive” is sufficient.

No replacement menu is recommended without rendered evidence that the current behavior fails the user task.

### Medium — current-page navigation state

The inspected base template does not expose an explicit `aria-current="page"` state on primary navigation links. A future bounded improvement may add current-location semantics if it can be implemented without duplicating route logic or regressing Hugo generation.

### Medium — external webfont dependency

The base template loads Google Fonts directly. This can affect privacy, availability, performance, and CSP strategy. Self-hosting or a system-font fallback strategy should be evaluated separately with measured bundle/cache and rendering evidence; it should not be mixed into a visual redesign prompt.

### Low — search stylesheet maintainability

`static/css/search.css` is compressed into a single line. It works as static CSS, but source maintainability and diff review are weaker. Reformatting should be an isolated non-functional change, not mixed with search UX changes.

### Unknown — visual hierarchy quality in rendered browsers

Static source shows a coherent design-token system and structured homepage hierarchy, but visual fidelity, actual contrast after font rendering, layout stability, overflow behavior, and browser-specific issues cannot be responsibly scored from source alone.

## Initial quality snapshot

Scores below evaluate **source-level implementation evidence**, not the live rendered product.

| Dimension | Score | Evidence status |
|---|---:|---|
| Prompt adherence | N/A | no single generation prompt being evaluated |
| UX quality | 7/10 | clear IA and search-first homepage; live task testing absent |
| Accessibility | 8/10 | strong source-level semantics; browser/AT evidence absent |
| Responsive quality | 8/10 | explicit breakpoints/reflow; device evidence absent |
| Code readiness | 8/10 | reusable tokens, semantic Hugo templates, minimal JS |
| Visual fidelity | N/A | no rendered target/reference comparison |
| Regression risk | 3/10 baseline | current source is bounded; large AI redesign would increase it materially |

This snapshot is `ITERATE`, not `PASS`, because rendered verification has not been observed.

## Priority order

1. **Protect the baseline before redesigning.**
2. Add prompt/evaluation instrumentation.
3. Test navigation and homepage/search behavior in rendered desktop/mobile widths.
4. Fix one evidenced defect at a time.
5. Only then consider visual refresh work.

## Pilot Prompt 01 — rendered homepage audit

```text
MODE: AUDIT

OBJECTIVE
Evaluate the current AISearchArab homepage without changing code and produce only evidence-backed UI defects.

TARGET
- Page: homepage
- Components: header/navigation, hero, search, content-path cards, latest-content cards, methodology CTA, footer

EVIDENCE REQUIRED
Use the current rendered build and current repository source. Capture/inspect at least desktop and mobile widths before scoring visual or responsive quality.

CONSTRAINTS
- Do not propose a redesign unless a specific defect is evidenced.
- Preserve Arabic RTL behavior.
- Preserve semantic HTML, keyboard support, focus-visible behavior, reduced motion, Static-First architecture, and current design tokens.

OUTPUT
For each defect provide:
1. severity;
2. observed evidence;
3. affected user task;
4. smallest viable fix;
5. regression risk;
6. acceptance criterion.

DO NOT MODIFY
No files in AUDIT mode.
```

## Pilot Prompt 02 — navigation current-location semantics

Run only if rendered/source review confirms it is useful.

```text
MODE: ACCESSIBILITY

OBJECTIVE
Expose the current page in primary navigation using correct semantic state without changing navigation structure or visual identity.

TARGET
- File: layouts/_default/baseof.html
- Component: .primary-nav

CHANGE
Add an evidence-based `aria-current="page"` state to the active navigation destination using Hugo-native route/page context.

DO NOT MODIFY
- navigation labels/order;
- responsive overflow strategy;
- colors/typography/spacing;
- JavaScript;
- header structure outside the minimum active-state logic.

ACCEPTANCE CRITERIA
1. Exactly the correct current primary destination receives `aria-current="page"` where applicable.
2. Homepage and section pages do not produce multiple current states.
3. Existing links and relative URLs remain valid.
4. Hugo build and relevant validation checks pass.
5. Keyboard/focus behavior remains unchanged.

REGRESSION RISK
Route matching may mark nested pages incorrectly. Test homepage, investigations, toolkits, methodology, corrections, and search.
```

## Pilot Prompt 03 — mobile navigation verification before redesign

```text
MODE: RESPONSIVE

OBJECTIVE
Determine whether the existing horizontally scrollable primary navigation is usable at narrow widths before replacing it.

TARGET
- .header-inner
- .primary-nav
- .primary-nav a

VERIFY FIRST
Test representative widths around 1040, 720, 420, and 320 CSS pixels.

CHECK
- all destinations reachable;
- keyboard focus remains visible while overflow scrolls;
- no clipping that makes a destination unreachable;
- touch targets are adequate;
- sticky header does not consume unreasonable viewport height;
- RTL scroll direction behaves correctly in supported browsers.

DECISION
If the current strategy passes, preserve it. If it fails, propose one bounded alternative and compare added JavaScript/complexity against the user benefit.

DO NOT REDESIGN OTHER HEADER ELEMENTS.
```

## Pilot Prompt 04 — webfont architecture experiment

```text
MODE: RED_TEAM

OBJECTIVE
Evaluate the external Google Fonts dependency independently from visual redesign.

COMPARE
A. current Google-hosted fonts;
B. self-hosted project fonts;
C. privacy/performance-oriented system-font fallback.

MEASURE OR VERIFY
- font request count and bytes;
- cache behavior;
- CSP implications;
- privacy/external-request implications;
- CLS/rendering behavior;
- Arabic readability.

DO NOT CHANGE TYPOGRAPHIC SCALE OR VISUAL HIERARCHY IN THIS EXPERIMENT.
```

## Definition of success for the pilot

The PromptOps pilot succeeds when:

- AI/coding agents receive the protocol as repository context;
- UI requests are decomposed into bounded changes;
- no agent claims visual/accessibility/performance PASS without observed evidence;
- successful and failed prompt variants are versioned in the external experiment registry;
- the first implementation change is selected from rendered evidence, not aesthetic preference.
