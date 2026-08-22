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
DEFAULT_MIGRATION = "20260816_0008"

REQUIRED_CONTROLS = (
    "security.dependency_audit_passed",
    "security.secret_scan_passed",
    "security.mfa_verified",
    "security.distributed_rate_limit_verified",
    "search.benchmark_verified",
    "performance.load_test_verified",
    "performance.slo_accepted",
    "database.managed_postgres_verified",
    "database.pitr_verified",
    "database.backup_verified",
    "database.restore_verified",
    "accessibility.wcag_22_aa",
    "external_review.security",
    "external_review.accessibility",
    "deployment.staging_verified",
    "deployment.rollback_verified",
    "deployment.dns_tls_verified",
    "deployment.observability_verified",
    "deployment.incident_drill_verified",
    "deployment.secrets_management_verified",
    "deployment.branch_governance_verified",
)
REQUIRED_CI = ("site", "api", "container")


@dataclass(slots=True)
class ReleaseEvidence:
    project: str
    generated_at: str
    source_head_sha: str
    tested_sha: str
    status: str
    migration: str
    base_sha: str | None = None
    repository: str | None = None
    branch: str | None = None
    pull_request: str | None = None
    workflow_run_id: int | None = None
    workflow_run_attempt: int | None = None
    openapi_sha256: str | None = None
    dependency_lock_sha256: str | None = None
    container_image_digest: str | None = None
    evidence_refs: dict[str, str] = field(default_factory=dict)
    ci: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    search: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    database: dict[str, Any] = field(default_factory=dict)
    accessibility: dict[str, Any] = field(default_factory=dict)
    external_review: dict[str, Any] = field(default_factory=dict)
    deployment: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    def _control_value(self, path: str) -> Any:
        section, key = path.split(".", 1)
        value = getattr(self, section)
        return value.get(key) if isinstance(value, dict) else None

    def derive_blockers(self) -> list[str]:
        blockers: list[str] = []
        for name in REQUIRED_CI:
            if self.ci.get(name) != "pass":
                blockers.append(f"ci.{name} is not verified pass")
        for path in REQUIRED_CONTROLS:
            if self._control_value(path) is not True:
                blockers.append(f"{path} is not verified")
        for item in self.blockers:
            normalized = item.strip()
            if normalized and normalized not in blockers:
                blockers.append(normalized)
        return blockers

    def validate(self) -> None:
        if self.status not in STATUS_VALUES:
            raise ValueError(f"unsupported release status: {self.status}")
        for field_name, sha in (
            ("source_head_sha", self.source_head_sha),
            ("tested_sha", self.tested_sha),
        ):
            if not HEX_SHA_RE.fullmatch(sha):
                raise ValueError(f"{field_name} must be a hexadecimal Git commit SHA")
        if self.base_sha is not None and not HEX_SHA_RE.fullmatch(self.base_sha):
            raise ValueError("base_sha must be a hexadecimal Git commit SHA")
        if self.pull_request and self.base_sha is None:
            raise ValueError("base_sha is required for pull-request evidence")
        if self.workflow_run_id is not None and self.workflow_run_id <= 0:
            raise ValueError("workflow_run_id must be positive")
        if self.workflow_run_attempt is not None and self.workflow_run_attempt <= 0:
            raise ValueError("workflow_run_attempt must be positive")

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
        if any(not key.strip() or not isinstance(value, str) or not value.strip() for key, value in self.evidence_refs.items()):
            raise ValueError("evidence_refs must map non-empty control names to non-empty references")

        self.blockers = self.derive_blockers()

        if self.status == "PRODUCTION_READY":
            missing: list[str] = []
            if self.pull_request:
                missing.append("production evidence must be generated from a non-PR release ref")
            if self.source_head_sha != self.tested_sha:
                missing.append("source_head_sha must equal tested_sha for the final production release ref")
            if self.migration != DEFAULT_MIGRATION:
                missing.append(f"migration must equal the current readiness revision {DEFAULT_MIGRATION}")
            if self.workflow_run_id is None:
                missing.append("workflow_run_id")
            if self.workflow_run_attempt is None:
                missing.append("workflow_run_attempt")
            for name in REQUIRED_CI:
                if self.ci.get(name) != "pass":
                    missing.append(f"ci.{name} must be pass")
            for path in REQUIRED_CONTROLS:
                if self._control_value(path) is not True:
                    missing.append(path)
                if not self.evidence_refs.get(path, "").strip():
                    missing.append(f"evidence_refs.{path}")
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
            if not isinstance(dataset_queries, int) or dataset_queries < 500:
                missing.append("search.dataset_queries must be >= 500")
            for metric in ("mrr_at_10", "ndcg_at_10", "recall_at_5", "recall_at_10", "precision_at_5", "zero_result_rate"):
                value = self.search.get(metric)
                if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                    missing.append(f"search.{metric} must be between 0 and 1")
            for metric in ("p50_ms", "p95_ms", "p99_ms"):
                value = self.performance.get(metric)
                if not isinstance(value, (int, float)) or float(value) < 0:
                    missing.append(f"performance.{metric} must be non-negative")
            error_rate = self.performance.get("error_rate")
            if not isinstance(error_rate, (int, float)) or not 0 <= float(error_rate) <= 1:
                missing.append("performance.error_rate must be between 0 and 1")
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


def _env_json_string_map(name: str) -> dict[str, str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or any(not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()):
        raise ValueError(f"{name} must be a JSON object mapping strings to strings")
    return value


def build_evidence() -> ReleaseEvidence:
    tested_sha = os.getenv("RELEASE_TESTED_SHA") or os.getenv("GITHUB_SHA") or os.getenv("RELEASE_COMMIT", "")
    source_head_sha = os.getenv("RELEASE_SOURCE_HEAD_SHA") or tested_sha
    manual_blockers = [item.strip() for item in os.getenv("RELEASE_BLOCKERS", "").split("|") if item.strip()]
    evidence = ReleaseEvidence(
        project="AISearcharab.com",
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_head_sha=source_head_sha,
        tested_sha=tested_sha,
        base_sha=os.getenv("RELEASE_BASE_SHA") or None,
        repository=os.getenv("GITHUB_REPOSITORY") or None,
        branch=os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME") or None,
        pull_request=os.getenv("RELEASE_PR") or None,
        workflow_run_id=_env_int("GITHUB_RUN_ID"),
        workflow_run_attempt=_env_int("GITHUB_RUN_ATTEMPT"),
        status=os.getenv("RELEASE_STATUS", "INTEGRATED_NOT_TESTED"),
        migration=os.getenv("RELEASE_MIGRATION", DEFAULT_MIGRATION),
        openapi_sha256=os.getenv("OPENAPI_SHA256") or None,
        dependency_lock_sha256=os.getenv("DEPENDENCY_LOCK_SHA256") or None,
        container_image_digest=os.getenv("CONTAINER_IMAGE_DIGEST") or None,
        evidence_refs=_env_json_string_map("RELEASE_EVIDENCE_REFS_JSON"),
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
        blockers=manual_blockers,
    )
    evidence.blockers = evidence.derive_blockers()
    return evidence


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
