#!/usr/bin/env python3
import re
from pathlib import Path

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PRIVATE_KEY_RE = re.compile(r'-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----')
SENSITIVE_TOKENS = [re.compile(r'AKIA[0-9A-Z]{16}'), re.compile(r'SK-[A-Za-z0-9]{32,}')]


def scan_tree(root='.'):
    issues = []
    for p in Path(root).rglob('*'):
        if p.is_file() and p.suffix not in ['.png', '.jpg', '.jpeg', '.gif', '.woff', '.woff2', '.ttf']:
            try:
                text = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            if EMAIL_RE.search(text):
                issues.append((str(p), 'email'))
            if PRIVATE_KEY_RE.search(text):
                issues.append((str(p), 'private_key'))
            for tok in SENSITIVE_TOKENS:
                if tok.search(text):
                    issues.append((str(p), 'possible_token'))
    return issues


if __name__ == '__main__':
    issues = scan_tree()
    if issues:
        print("Potential sensitive items found:")
        for f, kind in issues:
            print(f"- {f}: {kind}")
        raise SystemExit(2)
    else:
        print("No obvious sensitive items found.")
