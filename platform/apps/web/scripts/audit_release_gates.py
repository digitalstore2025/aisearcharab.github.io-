#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
PLATFORM = WEB.parents[1]
REPO = WEB.parents[2]
API = PLATFORM / 'apps/api/src/aisearcharab_api'


def fail(message: str) -> None:
    raise SystemExit(f'RELEASE GATE AUDIT FAILED: {message}')


for path in (WEB / 'src').rglob('*'):
    if not path.is_file() or path.suffix not in {'.ts', '.tsx', '.js', '.mjs'}:
        continue
    text = path.read_text(errors='ignore')
    if "'use server'" in text or '"use server"' in text:
        fail(f'unreviewed Server Action/server directive in {path.relative_to(WEB)}')
    if 'AISEARCH_API_BASE_URL' in text and 'src/server/' not in path.relative_to(WEB).as_posix():
        fail(f'upstream API origin escaped the server-only boundary: {path.relative_to(WEB)}')

approved_api_routes = {'src/app/api/health/route.ts'}
actual_api_routes = {
    path.relative_to(WEB).as_posix()
    for path in (WEB / 'src/app/api').rglob('route.ts')
}
if actual_api_routes != approved_api_routes:
    fail(f'API route surface changed without review: expected {sorted(approved_api_routes)}, got {sorted(actual_api_routes)}')

env_example = (WEB / '.env.example').read_text()
if 'AISEARCH_SEARCH_ENABLED=false' not in env_example:
    fail('search must remain fail-closed and disabled by default')

robots = (WEB / 'src/app/robots.ts').read_text()
layout = (WEB / 'src/app/layout.tsx').read_text()
next_config = (WEB / 'next.config.ts').read_text()
search_transport = (WEB / 'src/server/api/search.ts').read_text()
search_config = (WEB / 'src/server/api/config.ts').read_text()
search_results = (WEB / 'src/components/search/search-results.tsx').read_text()
if "disallow: '/'" not in robots or 'robots: { index: false, follow: false }' not in layout:
    fail('web foundation must remain noindex until canonical deployment is approved')
for marker in [
    'Content-Security-Policy',
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "Referrer-Policy', value: 'no-referrer'",
    "X-Robots-Tag', value: 'noindex, nofollow, noarchive'",
    'images: { unoptimized: true }',
]:
    if marker not in next_config:
        fail(f'security header/runtime hardening marker changed or disappeared: {marker}')
for forbidden in ['rewrites()', 'redirects()', 'dangerouslyAllowSVG']:
    if forbidden in next_config:
        fail(f'unreviewed Next.js network/image surface enabled: {forbidden}')

for marker in [
    "redirect: 'error'",
    'MAX_SEARCH_RESPONSE_BYTES = 256 * 1024',
    'response.body.getReader()',
    'assertSearchCall(query, offset)',
]:
    if marker not in search_transport:
        fail(f'search transport hardening marker changed or disappeared: {marker}')
if "process.env.NODE_ENV !== 'production'" not in search_config:
    fail('public-site origin must require HTTPS in production')
if search_results.count('prefetch={false}') < 2:
    fail('search pagination must not prefetch query-bearing pages')

workflow = (REPO / '.github/workflows/platform-web.yml').read_text()
for marker in [
    'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1',
    'actions/setup-node@820762786026740c76f36085b0efc47a31fe5020',
    'persist-credentials: false',
    'pnpm install --frozen-lockfile',
    'pnpm audit --audit-level high',
    'permissions:\n  contents: read',
]:
    if marker not in workflow:
        fail(f'CI supply-chain hardening marker changed or disappeared: {marker}')

dependabot = (REPO / '.github/dependabot.yml').read_text()
if 'package-ecosystem: "npm"' not in dependabot or 'directory: "/platform/apps/web"' not in dependabot:
    fail('Dependabot coverage for the web pnpm workspace is missing')

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

print('RELEASE GATE AUDIT OK: search, browser, CI supply-chain, backend auth, and noindex invariants remain enforced.')
