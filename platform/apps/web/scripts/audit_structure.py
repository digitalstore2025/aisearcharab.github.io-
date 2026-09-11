#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=['package.json','tsconfig.json','next.config.ts','eslint.config.mjs','ARCHITECTURE.md','DESIGN_SYSTEM.md','DATA_BOUNDARY.md','SECURITY_GATES.md','pnpm-lock.yaml','pnpm-workspace.yaml','.env.example','public/brand-mark.svg','src/app/layout.tsx','src/app/page.tsx','src/app/robots.ts','src/app/not-found.tsx','src/app/(workspace)/error.tsx','src/app/api/health/route.ts','src/components/navigation/nav-links.tsx','src/server/api/search.ts','src/lib/contracts/search.ts']
SECRET_PATTERNS=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(r'(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*["\'][^"\']{12,}["\']')]
CLIENT_FORBIDDEN_PATTERNS=[re.compile(r"(?:from\s+|import\s*)['\"]@/server(?:/|['\"])") ,re.compile(r"import\s+['\"]server-only['\"]"),re.compile(r"\bprocess\.env\b")]
EXPECTED_CLIENT_MODULES={'src/components/navigation/nav-links.tsx','src/app/(workspace)/error.tsx'}
def fail(message:str)->None: raise SystemExit(f'AUDIT FAILED: {message}')
def is_client_module(text:str)->bool:
    meaningful=[line.strip() for line in text.splitlines() if line.strip()][:5]
    return any(line in {"'use client';",'"use client";',"'use client'",'"use client"'} for line in meaningful)
for rel in REQUIRED:
    if not (ROOT/rel).is_file(): fail(f'missing required file: {rel}')
pkg=json.loads((ROOT/'package.json').read_text())
if pkg.get('dependencies',{}).get('next')!='16.3.4': fail('Next.js must be pinned to reviewed baseline 16.3.4')
if pkg.get('dependencies',{}).get('react')!=pkg.get('dependencies',{}).get('react-dom'): fail('react and react-dom versions must match')
if pkg.get('engines',{}).get('node')!='>=20.9.0': fail('Node engine baseline changed unexpectedly')
client_modules:set[str]=set()
for path in ROOT.rglob('*'):
    if not path.is_file() or any(part in {'.next','node_modules'} for part in path.parts): continue
    if path.suffix not in {'.ts','.tsx','.js','.mjs','.json','.md','.py','.css'}: continue
    text=path.read_text(errors='ignore'); rel=path.relative_to(ROOT)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text): fail(f'possible secret material in {rel}')
    if path.suffix in {'.ts','.tsx','.js','.mjs'} and is_client_module(text):
        client_modules.add(rel.as_posix())
        for pattern in CLIENT_FORBIDDEN_PATTERNS:
            if pattern.search(text): fail(f'client/server boundary violation in {rel}: {pattern.pattern}')
        if 'src/server' in rel.as_posix(): fail(f'client directive is forbidden under src/server: {rel}')
if client_modules!=EXPECTED_CLIENT_MODULES: fail(f'client-module budget changed: expected {sorted(EXPECTED_CLIENT_MODULES)}, got {sorted(client_modules)}')
print('AUDIT OK: structure, pinned baseline, secret scan, and client/server boundaries passed.')
