#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
PLATFORM = WEB.parents[1]
API = PLATFORM / 'apps/api/src/aisearcharab_api'


def fail(message: str) -> None:
    raise SystemExit(f'RELEASE GATE AUDIT FAILED: {message}')


for path in (WEB / 'src').rglob('*'):
    if not path.is_file() or path.suffix not in {'.ts', '.tsx', '.js', '.mjs'}:
        continue
    text = path.read_text(errors='ignore')
    if "'use server'" in text or '"use server"' in text:
        fail(f'unreviewed Server Action/server directive in {path.relative_to(WEB)}')

for forbidden in ('src/app/api/auth', 'src/app/api/session'):
    if (WEB / forbidden).exists():
        fail(f'auth BFF surface opened before proxy/throttle review: {forbidden}')

robots = (WEB / 'src/app/robots.ts').read_text()
if "disallow: '/'" not in robots:
    fail('web foundation must remain noindex until canonical deployment is approved')

routes_auth = (API / 'routes_auth.py').read_text()
auth_core = (API / 'auth.py').read_text()
routes_mfa = (API / 'routes_mfa.py').read_text()
config = (API / 'config.py').read_text()
required_markers = {
    'routes_auth.py': [
        'httponly=True',
        '"samesite": "strict"',
        'require_csrf',
        'enforce_login_throttle',
        'record_login_failure',
    ],
    'auth.py': [
        'PRIVILEGED_MFA_ROLES',
        'require_mfa_for_privileged',
        'x-csrf-token',
        'require_sensitive_mutation',
    ],
    'routes_mfa.py': ['require_base_csrf', 'verify_totp', 'recovery_code'],
    'config.py': ['TRUSTED_PROXY', 'session_cookie_name', 'csrf_cookie_name'],
}
for name, markers in required_markers.items():
    source = {'routes_auth.py': routes_auth, 'auth.py': auth_core, 'routes_mfa.py': routes_mfa, 'config.py': config}[name]
    for marker in markers:
        if marker not in source:
            fail(f'backend auth invariant changed or disappeared: {name}:{marker}')

print('RELEASE GATE AUDIT OK: no shadow mutations/auth surface; backend auth invariants and noindex gate remain enforced.')
