from __future__ import annotations

import json

import pytest

from scripts.release_evidence import ReleaseEvidence, build_evidence, main


def test_default_evidence_never_claims_production_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELEASE_COMMIT", "abcdef1234567890")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    evidence = build_evidence()
    assert evidence.status == "INTEGRATED_NOT_TESTED"
    assert evidence.security["mfa_verified"] is False
    assert evidence.database["restore_verified"] is False
    assert evidence.deployment["staging_verified"] is False


def test_production_ready_requires_external_gates() -> None:
    evidence = ReleaseEvidence(
        project="AISearcharab.com",
        generated_at="2026-08-10T00:00:00+00:00",
        commit="abcdef1234567890",
        status="PRODUCTION_READY",
        migration="20260807_0004",
    )
    with pytest.raises(ValueError, match="PRODUCTION_READY evidence incomplete"):
        evidence.validate()


def test_production_ready_rejects_nonempty_blockers() -> None:
    evidence = ReleaseEvidence(
        project="AISearcharab.com",
        generated_at="2026-08-10T00:00:00+00:00",
        commit="abcdef1234567890",
        status="PRODUCTION_READY",
        migration="20260807_0004",
        security={"mfa_verified": True, "distributed_rate_limit_verified": True},
        database={"managed_postgres_verified": True, "backup_verified": True, "restore_verified": True},
        accessibility={"wcag_22_aa": True},
        external_review={"security": True, "accessibility": True},
        deployment={
            "staging_verified": True,
            "rollback_verified": True,
            "dns_tls_verified": True,
            "observability_verified": True,
        },
        blockers=["independent review pending"],
    )
    with pytest.raises(ValueError, match="blockers must be empty"):
        evidence.validate()


def test_production_ready_accepts_complete_evidence() -> None:
    evidence = ReleaseEvidence(
        project="AISearcharab.com",
        generated_at="2026-08-10T00:00:00+00:00",
        commit="abcdef1234567890",
        status="PRODUCTION_READY",
        migration="20260807_0004",
        security={"mfa_verified": True, "distributed_rate_limit_verified": True},
        database={"managed_postgres_verified": True, "backup_verified": True, "restore_verified": True},
        accessibility={"wcag_22_aa": True},
        external_review={"security": True, "accessibility": True},
        deployment={
            "staging_verified": True,
            "rollback_verified": True,
            "dns_tls_verified": True,
            "observability_verified": True,
        },
    )
    evidence.validate()


def test_cli_writes_machine_readable_evidence(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELEASE_COMMIT", "abcdef1234567890")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    output = tmp_path / "release-evidence.json"
    monkeypatch.setattr("sys.argv", ["release_evidence.py", "--output", str(output)])
    assert main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"] == "AISearcharab.com"
    assert payload["status"] == "INTEGRATED_NOT_TESTED"
    assert payload["security"]["mfa_verified"] is False
