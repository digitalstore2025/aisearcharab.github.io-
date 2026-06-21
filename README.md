# aisearcharab.com

Arabic-first investigative journalism, OSINT, fact-checking, and data-analysis platform.

## Implemented

- Hugo static site with RTL layouts.
- Investigations, toolkits, methodology, and corrections sections.
- Structured source, claim, and entity records.
- JSON schemas and Python validation tests.
- Static JSON search index and Schema.org metadata.
- Privacy, terms, security, CODEOWNERS, Dependabot, CI, and custom domain configuration.

## Local checks

```bash
python -m unittest discover -s tests -v
python scripts/validate_data.py
hugo --minify --gc
```

See `docs/EXECUTIVE_BLUEPRINT.md` and `AGENTS.md` for project governance.
