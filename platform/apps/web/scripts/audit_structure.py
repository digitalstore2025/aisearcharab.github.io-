#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=['package.json','tsconfig.json','next.config.ts','eslint.config.mjs','playwright.config.ts','ARCHITECTURE.md','DESIGN_SYSTEM.md','DATA_BOUNDARY.md','SECURITY_GATES.md','HARDENING_BASELINE.md','SECURITY_TEST_MATRIX.md','RELEASE_CHECKLIST.md','pnpm-lock.yaml','pnpm-workspace.yaml','.env.example','public/brand-mark.svg','src/app/layout.tsx','src/app/page.tsx','src/app/robots.ts','src/app/not-found.tsx','src/app/(workspace)/error.tsx','src/app/api/health/route.ts','src/components/navigation/nav-links.tsx','src/server/api/search.ts','src/lib/contracts/search.ts','e2e/foundation.spec.ts','tests/search-security.test.ts']
SECRET_PATTERNS=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(r'(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*["\'][^"\']{12,}["\']'),re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b'),re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}\b'),re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'),re.compile(r'\bAKIA[0-9A-Z]{16}\b')]
CLIENT_FORBIDDEN_PATTERNS=[re.compile(r"(?:from\s+|import\s*)['\"]@/server(?:/|['\"])") ,re.compile(r"import\s+['\"]server-only['\"]"),re.compile(r"\bprocess\.env\b")]
DANGEROUS_SOURCE_PATTERNS=[re.compile(r'\bdangerouslySetInnerHTML\b'),re.compile(r'(?<![\w.])eval\s*\('),re.compile(r'\bnew\s+Function\s*\('),re.compile(r'\bdocument\.write\s*\(')]
EXPECTED_CLIENT_MODULES={'src/components/navigation/nav-links.tsx','src/app/(workspace)/error.tsx'}
TEXT_SUFFIXES={'.ts','.tsx','.js','.mjs','.json','.md','.py','.css','.yml','.yaml'}
SOURCE_SUFFIXES={'.ts','.tsx','.js','.mjs'}
def fail(message:str)->None: raise SystemExit(f'AUDIT FAILED: {message}')
def is_client_module(text:str)->bool:
    meaningful=[line.strip() for line in text.splitlines() if line.strip()][:5]
    return any(line in {"'use client';",'"use client";',"'use client'",'"use client"'} for line in meaningful)
for rel in REQUIRED:
    if not (ROOT/rel).is_file(): fail(f'missing required file: {rel}')
pkg=json.loads((ROOT/'package.json').read_text())
if pkg.get('dependencies',{}).get('next')!='16.3.4': fail('Next.js must be pinned to reviewed baseline 16.3.4')
if pkg.get('dependencies',{}).get('react')!='19.2.8' or pkg.get('dependencies',{}).get('react-dom')!='19.2.8': fail('React must remain on reviewed patched baseline 19.2.8')
if pkg.get('devDependencies',{}).get('@playwright/test')!='1.63.0': fail('Playwright must be pinned to reviewed baseline 1.63.0')
if pkg.get('devDependencies',{}).get('vitest')!='4.1.11': fail('Vitest must remain on patched baseline 4.1.11 or be deliberately re-reviewed')
if pkg.get('packageManager')!='pnpm@12.3.4': fail('pnpm must remain on reviewed baseline 12.3.4')
if pkg.get('engines',{}).get('node')!='>=20.9.0': fail('Node engine baseline changed unexpectedly')
for rel, marker in {
    'HARDENING_BASELINE.md':'No known Critical or High vulnerability remains within the tested code scope',
    'SECURITY_TEST_MATRIX.md':'Every newly fixed security defect must add at least one regression test',
    'RELEASE_CHECKLIST.md':'CodeQL JavaScript/TypeScript analysis passes release policy',
}.items():
    if marker not in (ROOT/rel).read_text(): fail(f'hardening governance marker changed or disappeared: {rel}:{marker}')
client_modules:set[str]=set()
for path in ROOT.rglob('*'):
    if not path.is_file() or any(part in {'.next','node_modules','playwright-report','test-results'} for part in path.parts): continue
    if path.suffix not in TEXT_SUFFIXES and not path.name.startswith('.env'): continue
    text=path.read_text(errors='ignore'); rel=path.relative_to(ROOT)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text): fail(f'possible secret material in {rel}')
    if path.suffix in SOURCE_SUFFIXES:
        for pattern in DANGEROUS_SOURCE_PATTERNS:
            if pattern.search(text): fail(f'unreviewed dangerous browser/code-execution sink in {rel}: {pattern.pattern}')
    if path.suffix in SOURCE_SUFFIXES and is_client_module(text):
        client_modules.add(rel.as_posix())
        for pattern in CLIENT_FORBIDDEN_PATTERNS:
            if pattern.search(text): fail(f'client/server boundary violation in {rel}: {pattern.pattern}')
        if 'src/server' in rel.as_posix(): fail(f'client directive is forbidden under src/server: {rel}')
if client_modules!=EXPECTED_CLIENT_MODULES: fail(f'client-module budget changed: expected {sorted(EXPECTED_CLIENT_MODULES)}, got {sorted(client_modules)}')
print('AUDIT OK: structure, patched baselines, hardening governance, secret scan, dangerous sinks, and client/server boundaries passed.')
