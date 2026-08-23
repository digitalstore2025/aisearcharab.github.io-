from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def current_checkout_identity(repo_root: str | Path) -> tuple[str, str]:
    root = Path(repo_root)
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Could not resolve the current checkout SHA.") from exc
    source_ref = os.getenv("GITHUB_REF", "").strip()
    if not source_ref:
        try:
            source_ref = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError("Could not resolve the current checkout ref; provide a branch/tag checkout or GITHUB_REF.") from exc
    if source_ref.startswith("refs/pull/"):
        raise ValueError("Pull-request refs cannot authorize production readiness.")
    if not source_ref.startswith(("refs/heads/", "refs/tags/")):
        raise ValueError(f"Unsupported release ref: {source_ref!r}")
    return sha, source_ref


def validate_release_evidence_artifact(
    text: str,
    repo_root: str | Path,
    *,
    expected_sha: str | None = None,
    expected_source_ref: str | None = None,
) -> dict[str, Any]:
    if expected_sha is None or expected_source_ref is None:
        expected_sha, expected_source_ref = current_checkout_identity(repo_root)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Release evidence must be a JSON object.")
    script = Path(repo_root) / "platform" / "apps" / "api" / "scripts" / "release_evidence.py"
    if not script.is_file():
        raise ValueError(f"Authoritative release-evidence script not found: {script}")
    module_name = "aisearcharab_authoritative_release_evidence"
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise ValueError("Could not load authoritative release-evidence contract.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        evidence = module.ReleaseEvidence(**payload)
        evidence.validate()
    finally:
        sys.modules.pop(module_name, None)
    if evidence.status != "PRODUCTION_READY":
        raise ValueError(f"Authoritative release status is {evidence.status!r}, not 'PRODUCTION_READY'.")
    if expected_source_ref.startswith("refs/pull/") or not expected_source_ref.startswith(("refs/heads/", "refs/tags/")):
        raise ValueError(f"Unsupported expected release ref: {expected_source_ref!r}")
    if evidence.source_ref != expected_source_ref:
        raise ValueError(f"Release evidence ref mismatch: artifact={evidence.source_ref!r}, expected={expected_source_ref!r}.")
    if evidence.tested_sha != expected_sha or evidence.source_head_sha != expected_sha:
        raise ValueError("Release evidence SHA mismatch: artifact must be bound to the current final checkout.")
    if evidence.blockers:
        raise ValueError("Authoritative release evidence still contains blockers.")
    return {"validated": True, "status": evidence.status, "source_ref": evidence.source_ref, "source_head_sha": evidence.source_head_sha, "tested_sha": evidence.tested_sha}
