# UI PromptOps System — AISearchArab

Status: pilot / evidence-gated
Date: 2026-08-19

## Purpose

This protocol governs AI-assisted design and frontend changes in AISearchArab. It converts vague visual requests into bounded, testable changes and prevents a design/coding agent from rebuilding unrelated approved UI.

It complements, and does not override, `AGENTS.md`, `docs/EXECUTIVE_BLUEPRINT.md`, security policy, repository tests, or human editorial review.

## Core operating model

Use this sequence:

`evidence -> audit -> specification -> atomic prompt -> implementation -> verification -> regression review -> next iteration`

Do not use:

`large vague prompt -> redesign everything -> subjective approval`

## Evidence rules

Before proposing a UI change, classify inputs as:

- **FACT** — directly observed in repository code, rendered evidence, test output, or supplied requirement.
- **INFERENCE** — supported conclusion that is not directly observed.
- **ASSUMPTION** — temporary premise required to proceed.
- **UNKNOWN** — not established with available evidence.

Never claim visual fidelity, accessibility compliance, performance success, browser compatibility, or production readiness without the corresponding evidence.

## Input contract

For every UI task, extract the smallest relevant set of:

- product goal;
- target user and job-to-be-done;
- target page/screen;
- target component;
- current state/evidence;
- requested outcome;
- Arabic/RTL implications;
- responsive implications;
- accessibility implications;
- performance/security implications;
- explicit exclusions;
- acceptance criteria.

If a missing item does not block safe execution, label the assumption and continue. Do not invent product requirements.

## Modes

Choose the narrowest valid mode:

1. `AUDIT` — inspect existing UI/prompt without changing code.
2. `FOUNDATION` — define product/design direction.
3. `SCREEN` — specify one screen.
4. `COMPONENT` — specify one component.
5. `REFINE` — make one bounded improvement.
6. `RTL` — fix directionality/localization behavior.
7. `RESPONSIVE` — fix reflow/breakpoint behavior.
8. `ACCESSIBILITY` — remediate an accessibility defect.
9. `DESIGN_TO_CODE` — convert an approved design/spec into implementation instructions.
10. `RED_TEAM` — adversarially test UX, accessibility, responsiveness, regression, maintainability, security, and performance.

## Atomic iteration contract

A refinement prompt MUST contain:

1. **Objective**
2. **Target page/screen**
3. **Target component**
4. **One major change**
5. **Current problem**
6. **Constraints**
7. **DO NOT MODIFY**
8. **Acceptance criteria**
9. **Regression risks**
10. **Verification commands/evidence required**

At most two changes may be combined only when tightly coupled. Do not bundle layout redesign, new components, typography, colors, copy restructuring, imagery, and responsive changes into one iteration.

## Approved baseline freeze

After a screen/component is accepted, agents must treat it as a versioned baseline:

> Preserve the current approved layout, information hierarchy, semantic structure, typography, spacing, navigation, design tokens, RTL behavior, accessibility behavior, and unrelated components. Modify only the explicitly named target.

A later prompt may override this only explicitly.

## AISearchArab frontend invariants

All changes must preserve these repository-level properties unless an approved ADR changes them:

- Arabic-first, `dir="rtl"` experience.
- Semantic HTML before decorative wrappers.
- WCAG 2.2 AA target.
- Keyboard operability and visible focus.
- `prefers-reduced-motion` support.
- Logical CSS properties for direction-aware layout where practical.
- Static-first architecture and minimal progressive JavaScript.
- No client-side framework for isolated behavior.
- No new dependency without measurable value.
- Visible structured data must match page content.
- No fabricated content, sources, metrics, test results, or UX research.

## Responsive contract

Do not write only “make it responsive.” State expected behavior for the affected ranges. For this repository, inspect the existing responsive system before creating another breakpoint.

For each changed component define, where relevant:

- stacking/reflow;
- navigation behavior;
- overflow strategy;
- touch target behavior;
- readable line length;
- table/card behavior;
- content priority;
- RTL behavior at narrow widths.

## Accessibility contract

For each UI change verify the affected subset of:

- semantic landmarks and heading hierarchy;
- accessible name/label;
- keyboard interaction;
- focus order and focus visibility;
- contrast;
- status/error announcements;
- touch target sizing;
- reduced motion;
- zoom/reflow;
- non-color cues;
- correct use of ARIA only where native semantics are insufficient.

## Design-to-code contract

An approved design is not production evidence. Implementation prompts must additionally specify:

- affected template/CSS/JS files;
- reuse of existing tokens/classes;
- data/state boundaries if applicable;
- security implications for user-controlled content;
- performance impact;
- test/validation requirements;
- rollback/regression risk.

## Quality rubric

Score only dimensions supported by evidence. Leave unobserved dimensions `N/A` rather than guessing.

| Dimension | Range | Meaning |
|---|---:|---|
| Prompt adherence | 0–10 | requested scope and constraints preserved |
| UX quality | 0–10 | task clarity, hierarchy, friction |
| Accessibility | 0–10 | relevant WCAG behavior evidenced |
| Responsive quality | 0–10 | reflow/overflow behavior evidenced |
| Code readiness | 0–10 | implementation clarity and maintainability |
| Visual fidelity | 0–10 / N/A | only with rendered reference/target evidence |
| Regression risk | 0–10 | 10 = highest risk |

### Quality gate

A UI change may be marked `PASS` only when:

- no unresolved Critical defect exists;
- Prompt Adherence >= 8;
- Accessibility >= 7 for the affected surface;
- Responsive Quality >= 8 when responsive behavior changes;
- Regression Risk <= 3;
- repository-required checks for the change have actually run and passed.

Use `ITERATE` for correctable gaps and `FAIL` for material requirement failure or regression.

## Reusable execution prompt

```text
MODE: <AUDIT|SCREEN|COMPONENT|REFINE|RTL|RESPONSIVE|ACCESSIBILITY|DESIGN_TO_CODE|RED_TEAM>

OBJECTIVE
<one measurable outcome>

EVIDENCE
- <file/render/test evidence>

TARGET
- Page: <page>
- Component: <component>

CURRENT PROBLEM
<one bounded problem>

CHANGE
<one major change>

CONSTRAINTS
- Preserve Static-First architecture.
- Preserve Arabic RTL semantics.
- Preserve WCAG 2.2 AA target.
- Reuse existing design tokens/classes where possible.
- Add no dependency unless justified by measurable value.

DO NOT MODIFY
- <explicit approved areas>

ACCEPTANCE CRITERIA
1. <observable criterion>
2. <observable criterion>
3. <test/evidence criterion>

REGRESSION RISKS
- <risk and mitigation>

VERIFY
- run the repository checks relevant to changed files;
- inspect rendered behavior at affected widths when UI changes;
- verify keyboard/focus semantics for interactive changes;
- report commands and observed results; never fabricate PASS.
```

## Learning loop

For every meaningful prompt experiment, record externally or in an approved evidence artifact:

- project;
- prompt name/version;
- exact prompt;
- model/tool;
- target page/component;
- output reference;
- scores;
- defects;
- regressions;
- successful pattern;
- failed pattern;
- next hypothesis.

Promote a pattern to reusable guidance only after repeated evidence across tasks or explicit human approval. One successful generation is not proof of general effectiveness.

## Versioning

Use `PromptName/vMajor.Minor.Patch`:

- Major: changes strategy/architecture.
- Minor: meaningful bounded improvement.
- Patch: narrow correction.

Do not overwrite a known-good prompt without retaining its previous version in the experiment registry.
