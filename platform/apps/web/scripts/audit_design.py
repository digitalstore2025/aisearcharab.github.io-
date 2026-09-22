#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / 'src/app/globals.css').read_text()

EXPECTED_BRAND = {
    'navy-deep': '#0b1f33',
    'teal': '#15616d',
    'teal-secondary': '#2c7a7b',
    'gold': '#d6a756',
}
PAIRS = [
    ('text', 'surface'),
    ('text-secondary', 'surface'),
    ('muted-text', 'surface'),
    ('surface', 'teal'),
    ('surface', 'navy-deep'),
    ('gold', 'navy-deep'),
    ('warning-text', 'surface'),
    ('error', 'surface'),
]

def fail(message: str) -> None:
    raise SystemExit(f'DESIGN AUDIT FAILED: {message}')

def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip('#')
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[return-value]

def channel(value: int) -> float:
    srgb = value / 255
    return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

def luminance(value: str) -> float:
    r, g, b = hex_to_rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)

tokens = {name: value.lower() for name, value in re.findall(r'--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;', CSS)}
for name, expected in EXPECTED_BRAND.items():
    if tokens.get(name) != expected:
        fail(f'brand token --{name} changed: expected {expected}, got {tokens.get(name)}')

for foreground, background in PAIRS:
    if foreground not in tokens or background not in tokens:
        fail(f'missing contrast token: {foreground}/{background}')
    ratio = contrast(tokens[foreground], tokens[background])
    if ratio < 4.5:
        fail(f'contrast {foreground}/{background} is {ratio:.2f}:1, below 4.5:1')
    print(f'PASS {foreground}/{background}: {ratio:.2f}:1')

required_routes = ['dashboard', 'search', 'sources', 'research', 'projects']
for route in required_routes:
    page = ROOT / 'src/app/(workspace)' / route / 'page.tsx'
    if not page.is_file():
        fail(f'missing workspace route: /{route}')

print('DESIGN AUDIT OK: brand identity, AA text contrast, and workspace routes passed.')
