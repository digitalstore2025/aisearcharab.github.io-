from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_VALUES = {
    "NOT_STARTED",
    "DESIGNED",
    "IMPLEMENTED_NOT_INTEGRATED",
    "INTEGRATED_NOT_TESTED",
    "TESTED_IN_STAGING",
    "EXTERNALLY_VERIFIED",
    "BLOCKED",
    "PRODUCTION_READY",
}
HEX_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(slots=True)
class ReleaseEvidence:
    project: str
    generated_at: str
    commit: str
    status: str
    migration: str
    branch: str | None = None
    pull_request: str | None = None
    openapi_sha256: str | None = None
    dependency_lock_sha256: str | None = None
    container_image_digest: str | None = None
    ci: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    search: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    database: dict[str, Any] = field(default_factory=dict)
    accessibility: dict[str, Any] = field(default_factory=dict)
    external_review: dict[str, Any] = field(default_factory=dict)
    deployment: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.status not in STATUS_VALUES:
            raise ValueError(f"unsupported release status: {self.status}")
        if not HEX_SHA_RE.fullmatch(self.commit):
            raise ValueError("commit must be a hexadecimal Git commit SHA")
        for field_name, digest in (
            ("openapi_sha256", self.openapi_sha256),
            ("dependency_lock_sha256", self.dependency_lock_sha256),
        ):
            if digest is not None and not SHA256_RE.fullmatch(digest):
                raise ValueError(f"{field_name} must be a 64-character SHA-256 digest")
        if self.container_image_digest is not None and not self.container_image_digest.startswith("sha256:"):
            raise ValueError("container_image_digest must use sha256:<digest> format")
        if self.container_image_digest is not None and not SHA256_RE.fullmatch(self.container_image_digest.removeprefix("sha256:")):
            raise ValueError("container_image_digest must contain a valid SHA-256 digest")

        if self.status == "PRODUCTION_READY":
            required_true = (
                ("security.dependency_audit_passed", self.security.get("dependency_audit_passed")),
                ("security.secret_scan_passed", self.security.get("secret_scan_passed")),
                ("security.mfa_verified", self.security.get("mfa_verified")),
                ("security.distributed_rate_limit_verified", self.security.get("distributed_rate_limit_verified")),
                ("search.benchmark_verified", self.search.get("benchmark_verified")),
                ("performance.load_test_verified", self.performance.get("load_test_verified")),
                ("performance.slo_accepted", self.performance.get("slo_accepted")),
                ("database.managed_postgres_verified", self.database.get("managed_postgres_verified")),
                ("database.pitr_verified", self.database.get("pitr_verified")),
                ("database.backup_verified", self.database.get("backup_verified")),
                ("database.restore_verified", self.database.get("restore_verified")),
                ("accessibility.wcag_22_aa", self.accessibility.get("wcag_22_aa")),
                ("external_review.security", self.external_review.get("security")),
                ("external_review.accessibility", self.external_review.get("accessibility")),
                ("deployment.staging_verified", self.deployment.get("staging_verified")),
                ("deployment.rollback_verified", self.deployment.get("rollback_verified")),
                ("deployment.dns_tls_verified", self.deployment.get("dns_tls_verified")),
                ("deployment.observability_verified", self.deployment.get("observability_verified")),
                ("deployment.incident_drill_verified", self.deployment.get("incident_drill_verified")),
                ("deployment.secrets_management_verified", self.deployment.get("secrets_management_verified")),
                ("deployment.branch_governance_verified", self.deployment.get("branch_governance_verified")),
            )
            missing = [name for name, value in required_true if value is not True]
            if self.security.get("critical_open") != 0:
                missing.append("security.critical_open must be 0")
            if self.security.get("high_open") != 0:
                missing.append("security.high_open must be 0")
            if not self.openapi_sha256:
                missing.append("openapi_sha256")
            if not self.dependency_lock_sha256:
                missing.append("dependency_lock_sha256")
            if not self.container_image_digest:
                missing.append("container_image_digest")
            dataset_queries = self.search.get("dataset_queries")
            if not isinstance(dataset_queries, int) or dataset_queries < 200:
                missing.append("search.dataset_queries must be >= 200")
            for metric in ("mrr_at_10", "ndcg_at_10", "recall_at_5", "recall_at_10", "precision_at_5", "zero_result_rate"):
                if self.search.get(metric) is None:
                    missing.append(f"search.{metric}")
            for metric in ("p50_ms", "p95_ms", "p99_ms", "error_rate"):
                if self.performance.get(metric) is None:
                    missing.append(f"performance.{metric}")
            if self.blockers:
                missing.append("blockers must be empty")
            if missing:
                raise ValueError("PRODUCTION_READY evidence incomplete: " + ", ".join(missing))


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return None if not value else float(value)


def _env_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return None if not value else int(value)


def build_evidence() -> ReleaseEvidence:
    blockers = [item.strip() for item in os.getenv("RELEASE_BLOCKERS", "").split("|") if item.strip()]
    return ReleaseEvidence(
        project="AISearcharab.com",
        generated_at=datetime.now(timezone.utc).isoformat(),
        commit=os.getenv("GITHUB_SHA") or os.getenv("RELEASE_COMMIT", ""),
        branch=os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME") or None,
        pull_request=os.getenv("RELEASE_PR") or None,
        status=os.getenv("RELEASE_STATUS", "INTEGRATED_NOT_TESTED"),
        migration=os.getenv("RELEASE_MIGRATION", "20260808_0005"),
        openapi_sha256=os.getenv("OPENAPI_SHA256") or None,
        dependency_lock_sha256=os.getenv("DEPENDENCY_LOCK_SHA256") or None,
        container_image_digest=os.getenv("CONTAINER_IMAGE_DIGEST") or None,
        ci={
            "site": os.getenv("CI_SITE_STATUS", "unknown"),
            "api": os.getenv("CI_API_STATUS", "unknown"),
            "container": os.getenv("CI_CONTAINER_STATUS", "unknown"),
        },
        security={
            "critical_open": _env_int("SECURITY_CRITICAL_OPEN"),
            "high_open": _env_int("SECURITY_HIGH_OPEN"),
            "dependency_audit_passed": _env_bool("DEPENDENCY_AUDIT_PASSED"),
            "mfa_verified": _env_bool("MFA_VERIFIED"),
            "distributed_rate_limit_verified": _env_bool("DISTRIBUTED_RATE_LIMIT_VERIFIED"),
            "secret_scan_passed": _env_bool("SECRET_SCAN_PASSED"),
        },
        search={
            "benchmark_verified": _env_bool("SEARCH_BENCHMARK_VERIFIED"),
            "dataset_queries": _env_int("SEARCH_DATASET_QUERIES"),
            "mrr_at_10": _env_float("SEARCH_MRR_AT_10"),
            "ndcg_at_10": _env_float("SEARCH_NDCG_AT_10"),
            "recall_at_5": _env_float("SEARCH_RECALL_AT_5"),
            "recall_at_10": _env_float("SEARCH_RECALL_AT_10"),
            "precision_at_5": _env_float("SEARCH_PRECISION_AT_5"),
            "zero_result_rate": _env_float("SEARCH_ZERO_RESULT_RATE"),
        },
        performance={
            "load_test_verified": _env_bool("LOAD_TEST_VERIFIED"),
            "slo_accepted": _env_bool("LOAD_SLO_ACCEPTED"),
            "p50_ms": _env_float("LOAD_P50_MS"),
            "p95_ms": _env_float("LOAD_P95_MS"),
            "p99_ms": _env_float("LOAD_P99_MS"),
            "error_rate": _env_float("LOAD_ERROR_RATE"),
        },
        database={
            "managed_postgres_verified": _env_bool("MANAGED_POSTGRES_VERIFIED"),
            "pitr_verified": _env_bool("PITR_VERIFIED"),
            "backup_verified": _env_bool("BACKUP_VERIFIED"),
            "restore_verified": _env_bool("RESTORE_VERIFIED"),
        },
        accessibility={"wcag_22_aa": _env_bool("WCAG_22_AA_VERIFIED")},
        external_review={
            "security": _env_bool("EXTERNAL_SECURITY_REVIEW_VERIFIED"),
            "accessibility": _env_bool("EXTERNAL_ACCESSIBILITY_REVIEW_VERIFIED"),
        },
        deployment={
            "staging_verified": _env_bool("STAGING_VERIFIED"),
            "dns_tls_verified": _env_bool("DNS_TLS_VERIFIED"),
            "rollback_verified": _env_bool("ROLLBACK_VERIFIED"),
            "observability_verified": _env_bool("OBSERVABILITY_VERIFIED"),
            "incident_drill_verified": _env_bool("INCIDENT_DRILL_VERIFIED"),
            "secrets_management_verified": _env_bool("SECRETS_MANAGEMENT_VERIFIED"),
            "branch_governance_verified": _env_bool("BRANCH_GOVERNANCE_VERIFIED"),
        },
        blockers=blockers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate auditable AISearcharab release evidence.")
    parser.add_argument("--output", default="release-evidence.json")
    args = parser.parse_args()
    evidence = build_evidence()
    evidence.validate()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(asdict(evidence), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"release evidence written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
