#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = WEB_ROOT.parent / 'api'
SCHEMA_PATH = API_ROOT / 'src/aisearcharab_api/schemas.py'
MAIN_PATH = API_ROOT / 'src/aisearcharab_api/main.py'

EXPECTED = {
    'SearchResult': {'slug', 'url', 'title', 'summary', 'section', 'language', 'published_at', 'score', 'matched_fields', 'source_authority'},
    'SearchResponse': {'query', 'normalized_query', 'algorithm_version', 'retrieval_mode', 'total', 'limit', 'offset', 'took_ms', 'results'},
}

def fail(message: str) -> None:
    raise SystemExit(f'API CONTRACT AUDIT FAILED: {message}')

if not SCHEMA_PATH.is_file() or not MAIN_PATH.is_file():
    fail('FastAPI source files are missing')

schema_text = SCHEMA_PATH.read_text()
tree = ast.parse(schema_text)
classes: dict[str, set[str]] = {}
for node in tree.body:
    if isinstance(node, ast.ClassDef):
        classes[node.name] = {
            item.target.id
            for item in node.body
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
        }

for model, expected_fields in EXPECTED.items():
    actual = classes.get(model)
    if actual is None:
        fail(f'missing backend model {model}')
    missing = expected_fields - actual
    if missing:
        fail(f'{model} lost required fields: {sorted(missing)}')

if '_validate_local_url_path' not in schema_text or '@field_validator("url")' not in schema_text:
    fail('backend search-result URL path hardening changed or disappeared')

main_text = MAIN_PATH.read_text()
for marker in ['api_prefix}/search', 'max_length=120', 'offset: int = Query(default=0, ge=0, le=10_000)']:
    if marker not in main_text:
        fail(f'backend search route contract marker changed: {marker}')

print('API CONTRACT AUDIT OK: FastAPI search route and local-path security contract remain compatible with the web client.')
