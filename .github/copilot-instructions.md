# GitHub Copilot Instructions — aisearcharab.com

## Project context

This repository builds `aisearcharab.com`, an Arabic-first platform for investigative journalism, OSINT, fact-checking, data analysis, and research tools.

The intended architecture is Static-First:

- Hugo for site generation.
- Markdown for editorial content.
- JSON/YAML for sources, claims, entities, datasets, and provenance.
- Python for validation, transformation, analysis, and local research utilities.
- GitHub Actions for CI/CD and scheduled validation.
- GitHub Pages for static hosting.

Follow these references in order:

1. `docs/EXECUTIVE_BLUEPRINT.md`
2. `AGENTS.md`
3. Existing schemas, tests, and repository policies.

## Core rules

- Do not fabricate sources, citations, statistics, quotes, people, organizations, files, or test results.
- Do not represent an inference as a verified fact.
- Do not add credentials, private evidence, or sensitive source identities to the repository.
- Do not publish AI-generated editorial conclusions without an explicit human-review state.
- Prefer primary sources and record provenance metadata.
- Prefer static generation and precomputation over runtime services.
- Avoid new dependencies unless they provide measurable value.
- Keep JavaScript minimal and progressively enhanced.
- Preserve Arabic RTL behavior, semantic HTML, accessibility, and performance.

## Expected structure

```text
content/
data/
layouts/
assets/
static/
scripts/
agents/
tests/
docs/
.github/workflows/
```

Do not create duplicate directories or parallel architectures for the same responsibility.

## Content conventions

Investigative content should expose structured metadata for:

- question
- hypothesis
- methodology
- authors and reviewers
- sources
- claims
- entities
- confidence
- limitations
- right-of-reply status
- correction history
- publication and last-verification dates

Use ISO 8601 dates and stable lowercase hyphenated IDs.

## Source and claim handling

A source record should support, where applicable:

- stable ID
- title and publisher
- original URL
- archive URL
- publication date
- access date
- source type
- language
- reliability classification
- integrity hash
- limitations and notes

A claim record should distinguish verified facts, estimates, inferences, and third-party allegations. Include confidence and human-review status. Do not silently upgrade uncertain evidence.

## Python requirements

- Use the Python version configured by the repository.
- Add type hints to public functions.
- Separate file or network input from parsing and analysis.
- Validate external input.
- Use explicit timeouts and bounded retries.
- Make scripts idempotent where practical.
- Emit machine-readable run reports for research utilities.
- Respect access restrictions and source terms.
- Add tests for parsers, validators, transformations, and error paths.

## Hugo and frontend requirements

- Arabic and RTL are the default experience.
- Use semantic HTML and native browser capabilities first.
- Target WCAG 2.2 AA.
- Ensure keyboard navigation and visible focus states.
- Support `prefers-reduced-motion`.
- Do not use color as the only signal.
- Glassmorphism must not reduce contrast or readability.
- Use responsive, optimized images.
- Do not add client-side frameworks for isolated UI behavior.
- Structured data must match visible page content.

## Security requirements

- Apply least privilege to GitHub Actions.
- Do not expose sensitive values in code, pages, fixtures, or logs.
- Treat remote content and user-controlled strings as untrusted.
- Escape or sanitize generated HTML.
- Keep automation conservative when processing external contributions.
- Pin dependencies and actions according to repository policy.
- Keep unpublished investigations and sensitive evidence outside the public repository.

## Testing and validation

Before describing work as complete, run the relevant available checks:

- Hugo build
- unit and integration tests
- schema validation
- link validation
- Markdown and HTML linting
- secret scanning
- dependency and security checks
- accessibility checks for UI changes
- performance budget checks for frontend changes

Never claim a command passed unless it was actually run and its output was observed.

## Implementation summaries

State:

1. Files changed.
2. Technical decisions made.
3. Tests or checks executed and their results.
4. Remaining limitations, risks, or unverified assumptions.
