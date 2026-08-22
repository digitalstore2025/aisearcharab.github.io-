from __future__ import annotations

import json

import pytest

from aisearcharab_api.main import EXPECTED_ALEMBIC_REVISION
from scripts.release_evidence import DEFAULT_MIGRATION, REQUIRED_CONTROLS, ReleaseEvidence, build_evidence, main

DIGEST = "a" * 64
SHA = "abcdef1234567890"
BASE_SHA = "1234567890abcdef"


def complete_evidence(**overrides) -> ReleaseEvidence:
    values = {
        "project": "AISearcharab.com",
        "generated_at": "2026-08-10T00:00:00+00:00",
        "source_head_sha": SHA,
        "tested_sha": SHA,
        "status": "PRODUCTION_READY",
        "migration": EXPECTED_ALEMBIC_REVISION,
        "workflow_run_id": 12345,
        "workflow_run_attempt": 1,
        "openapi_sha256": DIGEST,
        "dependency_lock_sha256": DIGEST,
        "container_image_digest": f"sha256:{DIGEST}",
        "evidence_refs": {path: f"artifact://{path}" for path in REQUIRED_CONTROLS},
        "ci": {"site": "pass", "api": "pass", "container": "pass"},
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
            "dataset_queries": 500,
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


def test_release_evidence_default_migration_matches_runtime_readiness() -> None:
    assert DEFAULT_MIGRATION == EXPECTED_ALEMBIC_REVISION


def test_default_evidence_never_claims_production_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELEASE_COMMIT", SHA)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    evidence = build_evidence()
    assert evidence.status == "INTEGRATED_NOT_TESTED"
    assert evidence.migration == EXPECTED_ALEMBIC_REVISION
    assert evidence.source_head_sha == SHA
    assert evidence.tested_sha == SHA
    assert evidence.security["mfa_verified"] is False
    assert evidence.search["benchmark_verified"] is False
    assert evidence.database["restore_verified"] is False
    assert evidence.deployment["staging_verified"] is False
    assert "deployment.staging_verified is not verified" in evidence.blockers


def test_invalid_source_sha_is_rejected() -> None:
    evidence = complete_evidence(source_head_sha="not-a-sha")
    with pytest.raises(ValueError, match="source_head_sha"):
        evidence.validate()


def test_invalid_tested_sha_is_rejected() -> None:
    evidence = complete_evidence(tested_sha="not-a-sha")
    with pytest.raises(ValueError, match="tested_sha"):
        evidence.validate()


def test_pr_evidence_requires_base_sha() -> None:
    evidence = complete_evidence(status="INTEGRATED_NOT_TESTED", pull_request="13", base_sha=None)
    with pytest.raises(ValueError, match="base_sha is required"):
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
        source_head_sha=SHA,
        tested_sha=SHA,
        status="PRODUCTION_READY",
        migration=EXPECTED_ALEMBIC_REVISION,
    )
    with pytest.raises(ValueError, match="PRODUCTION_READY evidence incomplete"):
        evidence.validate()


def test_production_ready_is_forbidden_from_pull_request() -> None:
    evidence = complete_evidence(pull_request="13", base_sha=BASE_SHA)
    with pytest.raises(ValueError, match="non-PR release ref"):
        evidence.validate()


def test_production_ready_requires_final_sha_to_match_tested_sha() -> None:
    evidence = complete_evidence(source_head_sha=BASE_SHA)
    with pytest.raises(ValueError, match="source_head_sha must equal tested_sha"):
        evidence.validate()


def test_production_ready_rejects_migration_mismatch() -> None:
    evidence = complete_evidence(migration="20260808_0005")
    with pytest.raises(ValueError, match="migration must equal the current readiness revision"):
        evidence.validate()


def test_production_ready_requires_evidence_reference_for_true_control() -> None:
    refs = {path: f"artifact://{path}" for path in REQUIRED_CONTROLS}
    refs.pop("database.restore_verified")
    evidence = complete_evidence(evidence_refs=refs)
    with pytest.raises(ValueError, match=r"evidence_refs\.database\.restore_verified"):
        evidence.validate()


def test_production_ready_requires_real_search_dataset_size() -> None:
    search = complete_evidence().search.copy()
    search["dataset_queries"] = 7
    evidence = complete_evidence(search=search)
    with pytest.raises(ValueError, match="dataset_queries must be >= 500"):
        evidence.validate()


def test_production_ready_rejects_invalid_metric_ranges() -> None:
    performance = complete_evidence().performance.copy()
    performance["error_rate"] = 1.5
    evidence = complete_evidence(performance=performance)
    with pytest.raises(ValueError, match="performance.error_rate must be between 0 and 1"):
        evidence.validate()


def test_blockers_are_derived_from_unverified_controls() -> None:
    security = complete_evidence().security.copy()
    security["mfa_verified"] = False
    evidence = complete_evidence(status="INTEGRATED_NOT_TESTED", security=security, blockers=[])
    evidence.validate()
    assert "security.mfa_verified is not verified" in evidence.blockers


def test_production_ready_accepts_complete_attested_evidence() -> None:
    complete_evidence().validate()


def test_cli_writes_machine_readable_evidence(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELEASE_COMMIT", SHA)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    output = tmp_path / "release-evidence.json"
    monkeypatch.setattr("sys.argv", ["release_evidence.py", "--output", str(output)])
    assert main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"] == "AISearcharab.com"
    assert payload["status"] == "INTEGRATED_NOT_TESTED"
    assert payload["migration"] == EXPECTED_ALEMBIC_REVISION
    assert payload["source_head_sha"] == SHA
    assert payload["tested_sha"] == SHA
    assert payload["security"]["mfa_verified"] is False
    assert payload["deployment"]["incident_drill_verified"] is False
    assert payload["blockers"]
