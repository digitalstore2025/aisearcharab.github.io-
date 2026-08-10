from __future__ import annotations

import json

import pytest

from scripts.release_evidence import ReleaseEvidence, build_evidence, main

DIGEST = "a" * 64


def complete_evidence(**overrides) -> ReleaseEvidence:
    values = {
        "project": "AISearcharab.com",
        "generated_at": "2026-08-10T00:00:00+00:00",
        "commit": "abcdef1234567890",
        "status": "PRODUCTION_READY",
        "migration": "20260808_0005",
        "openapi_sha256": DIGEST,
        "dependency_lock_sha256": DIGEST,
        "container_image_digest": f"sha256:{DIGEST}",
        "security": {
            "critical_open": 0,
            "high_open": 0,
            "dependency_audit_passed": True,
            "secret_scan_passed": True,
            "mfa_verified": True,
            "distributed_rate_limit_verified": True,
        },
        "search": {
            "benchmark_verified": True,
            "dataset_queries": 200,
            "mrr_at_10": 0.8,
            "ndcg_at_10": 0.8,
            "recall_at_5": 0.75,
            "recall_at_10": 0.85,
            "precision_at_5": 0.5,
            "zero_result_rate": 0.1,
        },
        "performance": {
            "load_test_verified": True,
            "slo_accepted": True,
            "p50_ms": 100.0,
            "p95_ms": 300.0,
            "p99_ms": 600.0,
            "error_rate": 0.0,
        },
        "database": {
            "managed_postgres_verified": True,
            "pitr_verified": True,
            "backup_verified": True,
            "restore_verified": True,
        },
        "accessibility": {"wcag_22_aa": True},
        "external_review": {"security": True, "accessibility": True},
        "deployment": {
            "staging_verified": True,
            "rollback_verified": True,
            "dns_tls_verified": True,
            "observability_verified": True,
            "incident_drill_verified": True,
            "secrets_management_verified": True,
            "branch_governance_verified": True,
        },
    }
    values.update(overrides)
    return ReleaseEvidence(**values)


def test_default_evidence_never_claims_production_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELEASE_COMMIT", "abcdef1234567890")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    evidence = build_evidence()
    assert evidence.status == "INTEGRATED_NOT_TESTED"
    assert evidence.migration == "20260808_0005"
    assert evidence.security["mfa_verified"] is False
    assert evidence.search["benchmark_verified"] is False
    assert evidence.database["restore_verified"] is False
    assert evidence.deployment["staging_verified"] is False


def test_invalid_commit_sha_is_rejected() -> None:
    evidence = complete_evidence(commit="not-a-sha")
    with pytest.raises(ValueError, match="hexadecimal Git commit SHA"):
        evidence.validate()


def test_invalid_sha256_evidence_is_rejected() -> None:
    evidence = complete_evidence(openapi_sha256="bad")
    with pytest.raises(ValueError, match="openapi_sha256"):
        evidence.validate()


def test_invalid_container_digest_is_rejected() -> None:
    evidence = complete_evidence(container_image_digest="sha256:bad")
    with pytest.raises(ValueError, match="container_image_digest"):
        evidence.validate()


def test_production_ready_requires_external_gates() -> None:
    evidence = ReleaseEvidence(
        project="AISearcharab.com",
        generated_at="2026-08-10T00:00:00+00:00",
        commit="abcdef1234567890",
        status="PRODUCTION_READY",
        migration="20260808_0005",
    )
    with pytest.raises(ValueError, match="PRODUCTION_READY evidence incomplete"):
        evidence.validate()


def test_production_ready_requires_real_search_dataset_size() -> None:
    evidence = complete_evidence(search={
        "benchmark_verified": True,
        "dataset_queries": 7,
        "mrr_at_10": 1.0,
        "ndcg_at_10": 1.0,
        "recall_at_5": 1.0,
        "recall_at_10": 1.0,
        "precision_at_5": 0.2,
        "zero_result_rate": 0.0,
    })
    with pytest.raises(ValueError, match="dataset_queries must be >= 200"):
        evidence.validate()


def test_production_ready_rejects_nonempty_blockers() -> None:
    evidence = complete_evidence(blockers=["independent review pending"])
    with pytest.raises(ValueError, match="blockers must be empty"):
        evidence.validate()


def test_production_ready_accepts_complete_evidence() -> None:
    complete_evidence().validate()


def test_cli_writes_machine_readable_evidence(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELEASE_COMMIT", "abcdef1234567890")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    output = tmp_path / "release-evidence.json"
    monkeypatch.setattr("sys.argv", ["release_evidence.py", "--output", str(output)])
    assert main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"] == "AISearcharab.com"
    assert payload["status"] == "INTEGRATED_NOT_TESTED"
    assert payload["migration"] == "20260808_0005"
    assert payload["security"]["mfa_verified"] is False
    assert payload["deployment"]["incident_drill_verified"] is False
