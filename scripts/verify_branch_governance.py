#!/usr/bin/env python3
"""Fail-closed verification for the minimum live governance state of `main`.

The script intentionally distinguishes repository configuration evidence from CI success.
It consumes the JSON returned by GitHub's `GET /repos/{owner}/{repo}/branches/main`
and exits non-zero unless GitHub reports the branch as protected.

This is a minimum enforcement floor, not full production-readiness proof. Full closure
also requires the controls tracked in Issue #97 (PR-only landing, required checks,
review policy, stale-approval dismissal, conversation resolution, force-push/deletion
protection, and controlled bypass).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class GovernanceError(ValueError):
    """Raised when live branch evidence does not meet the governance floor."""


def validate_branch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate GitHub branch JSON and return normalized evidence.

    Fail closed on malformed/unexpected payloads. The only passing state is an exact
    `main` payload with `protected is True`.
    """

    if not isinstance(payload, dict):
        raise GovernanceError("unexpected_payload_type")

    if payload.get("name") != "main":
        raise GovernanceError("unexpected_branch_payload")

    protected = payload.get("protected")
    if protected is not True:
        raise GovernanceError("main_is_not_protected")

    commit = payload.get("commit")
    if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str):
        raise GovernanceError("missing_commit_sha")

    sha = commit["sha"].strip()
    if len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
        raise GovernanceError("invalid_commit_sha")

    return {
        "branch": "main",
        "protected": True,
        "commit_sha": sha.lower(),
        "minimum_governance_floor": "PASS",
        "production_ready": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceError("unreadable_or_invalid_json") from exc

    if not isinstance(payload, dict):
        raise GovernanceError("unexpected_payload_type")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch-json", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        evidence = validate_branch_payload(_load_json(args.branch_json))
    except GovernanceError as exc:
        print(f"branch_governance=fail reason={exc}")
        return 2

    rendered = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    print(f"branch_governance=pass evidence={rendered}")
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
