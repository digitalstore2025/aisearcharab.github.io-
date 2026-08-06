#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "public", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".gz", ".tar", ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4",
}
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("provider_secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b", re.IGNORECASE)),
)


def _eligible(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in SKIP_DIRS for part in relative.parts[:-1]):
        return False
    return path.suffix.casefold() not in SKIP_SUFFIXES


def scan_tree(root: str | Path = ".") -> list[tuple[str, str]]:
    base = Path(root).resolve()
    findings: list[tuple[str, str]] = []
    for path in base.rglob("*"):
        if not path.is_file() or not _eligible(path, base):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for kind, pattern in PATTERNS:
            if pattern.search(text):
                findings.append((str(path.relative_to(base)), kind))
    return findings


def main() -> int:
    findings = scan_tree()
    if not findings:
        print("Sensitive-data scan passed.")
        return 0
    print("Potential secrets detected (values redacted):")
    for path, kind in findings:
        print(f"- {path}: {kind}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
