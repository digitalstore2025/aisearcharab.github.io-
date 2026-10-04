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
    "script-src-attr 'none'",
    'upgrade-insecure-requests',
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

# PR verification is owned by a canonical workflow that is installed on main
# independently of the application PR. This avoids self-approving CI policy.
web_security = (REPO / '.github/workflows/web-security.yml').read_text()
for marker in [
    'name: Web security gate',
    'platform/apps/web/**',
    'platform/apps/api/**',
    'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1',
    'actions/setup-node@820762786026740c76f36085b0efc47a31fe5020',
    'actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a',
    'node-version: "24.21.0"',
    "if(!v.startsWith('24.'))",
    'persist-credentials: false',
    'pnpm install --frozen-lockfile',
    'pnpm audit --audit-level moderate',
    'pnpm list --prod --json --depth Infinity',
    'scripts/test_generate_cyclonedx_sbom.py',
    'scripts/generate_cyclonedx_sbom.py',
    'Validate SBOM package evidence',
    'web-cyclonedx-sbom',
    'python3 scripts/audit_structure.py',
    'python3 scripts/audit_design.py',
    'python3 scripts/audit_api_contract.py',
    'python3 scripts/audit_release_gates.py',
    'pnpm e2e',
    'name: web-codeql (${{ matrix.language }})',
    '- javascript-typescript',
    '- python',
    'security-events: write',
    'github/codeql-action/init@b96794f015dfd88f77b49b1c93e0fa7110f94c63',
    'github/codeql-action/analyze@b96794f015dfd88f77b49b1c93e0fa7110f94c63',
    'queries: security-extended',
]:
    if marker not in web_security:
        fail(f'canonical web security marker changed or disappeared: {marker}')
if 'permissions:\n  contents: read' not in web_security:
    fail('canonical web gate must keep top-level contents read-only permission')

# GitHub Actions definitions need an independent preflight because invalid YAML
# can prevent the broken workflow from creating a run at all.
workflow_lint = (REPO / '.github/workflows/workflow-lint.yml').read_text()
for marker in [
    'name: Workflow lint',
    '.github/workflows/**',
    'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1',
    'persist-credentials: false',
    'version="1.7.12"',
    'actionlint_${version}_linux_amd64.tar.gz',
    '8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8',
    'sha256sum --check --strict',
    "/tmp/actionlint/actionlint -color -ignore 'SC2129'",
]:
    if marker not in workflow_lint:
        fail(f'workflow preflight marker changed or disappeared: {marker}')
if 'permissions:\n  contents: read' not in workflow_lint:
    fail('workflow lint gate must keep top-level contents read-only permission')

dependabot = (REPO / '.github/dependabot.yml').read_text()
if 'package-ecosystem: "npm"' not in dependabot or 'directory: "/platform/apps/web"' not in dependabot:
    fail('Dependabot coverage for the web pnpm workspace is missing')

# PR CodeQL is enforced by the canonical Web security gate above. Keep this
# separate workflow for scheduled/default-branch rescans only, avoiding duplicate
# PR scans and invalid workflow-level matrix references.
codeql = (REPO / '.github/workflows/codeql.yml').read_text()
for marker in [
    'name: Scheduled CodeQL',
    'branches: ["main"]',
    'cron: "23 3 * * 1"',
    'group: codeql-${{ github.workflow }}-${{ github.ref }}',
    'github/codeql-action/init@b96794f015dfd88f77b49b1c93e0fa7110f94c63',
    'github/codeql-action/analyze@b96794f015dfd88f77b49b1c93e0fa7110f94c63',
    'language: ["javascript-typescript", "python"]',
    'queries: security-extended',
    'security-events: write',
    'persist-credentials: false',
]:
    if marker not in codeql:
        fail(f'CodeQL scheduled/default-branch security marker changed or disappeared: {marker}')
if 'pull_request:' in codeql:
    fail('scheduled CodeQL must not duplicate canonical PR CodeQL analysis')
if '${{ matrix.language }}' in codeql.split('jobs:', 1)[0]:
    fail('workflow-level CodeQL configuration must not reference matrix context')

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

print('RELEASE GATE AUDIT OK: search, browser, CSP, supported Node runtime, SBOM evidence, canonical PR verification/CodeQL, workflow preflight, scheduled CodeQL, backend auth, and noindex invariants remain enforced.')
