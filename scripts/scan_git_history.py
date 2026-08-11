#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from collections import defaultdict

from scan_sensitive_data import PATTERNS

MAX_BLOB_BYTES = 2_000_000


def _git(*args: str, text: bool = False) -> bytes | str:
    return subprocess.check_output(["git", *args], text=text, stderr=subprocess.DEVNULL)


def main() -> int:
    try:
        objects = str(_git("rev-list", "--objects", "--all", text=True)).splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Git history scan could not enumerate repository objects.")
        return 2

    paths_by_sha: dict[str, set[str]] = defaultdict(set)
    for line in objects:
        sha, _, path = line.partition(" ")
        if path:
            paths_by_sha[sha].add(path)

    findings: set[tuple[str, str]] = set()
    checked_blobs = 0
    for sha, paths in paths_by_sha.items():
        try:
            if str(_git("cat-file", "-t", sha, text=True)).strip() != "blob":
                continue
            size = int(str(_git("cat-file", "-s", sha, text=True)).strip())
            if size > MAX_BLOB_BYTES:
                continue
            raw = bytes(_git("cat-file", "blob", sha))
        except (subprocess.CalledProcessError, ValueError):
            continue
        if b"\x00" in raw:
            continue
        text = raw.decode("utf-8", errors="ignore")
        checked_blobs += 1
        for kind, pattern in PATTERNS:
            if pattern.search(text):
                display_path = sorted(paths)[0] if paths else "<historical-blob>"
                findings.add((display_path, kind))

    if findings:
        print("Potential secrets exist in reachable Git history (values redacted):")
        for path, kind in sorted(findings):
            print(f"- {path}: {kind}")
        return 2

    print(f"Git history sensitive-data scan passed ({checked_blobs} text blobs checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
