#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'package.json', 'tsconfig.json', 'next.config.ts', 'eslint.config.mjs',
    'src/app/layout.tsx', 'src/app/page.tsx', 'src/app/api/health/route.ts',
]
SECRET_PATTERNS = [
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*["\'][^"\']{12,}["\']'),
]


def fail(message: str) -> None:
    raise SystemExit(f'AUDIT FAILED: {message}')

for rel in REQUIRED:
    if not (ROOT / rel).is_file():
        fail(f'missing required file: {rel}')

pkg = json.loads((ROOT / 'package.json').read_text())
if pkg.get('dependencies', {}).get('next') != '16.3.4':
    fail('Next.js must be pinned to reviewed baseline 16.3.4')
if pkg.get('dependencies', {}).get('react') != pkg.get('dependencies', {}).get('react-dom'):
    fail('react and react-dom versions must match')
if pkg.get('engines', {}).get('node') != '>=20.9.0':
    fail('Node engine baseline changed unexpectedly')

for path in ROOT.rglob('*'):
    if not path.is_file() or any(part in {'.next', 'node_modules'} for part in path.parts):
        continue
    if path.suffix not in {'.ts', '.tsx', '.js', '.mjs', '.json', '.md', '.py', '.css'}:
        continue
    text = path.read_text(errors='ignore')
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            fail(f'possible secret material in {path.relative_to(ROOT)}')

print('AUDIT OK: required structure, pinned baseline, and basic secret scan passed.')
