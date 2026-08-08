from __future__ import annotations

import json
from datetime import date

import pytest

from scripts.audit_runtime_dependencies import ExceptionRule, evaluate, load_exceptions, normalize_audit_payload


def rule(*, services: frozenset[str] = frozenset({"pypi"})) -> ExceptionRule:
    return ExceptionRule(
        vulnerability_id="CVE-2099-0001",
        package="example-package",
        version="1.2.3",
        services=services,
        expires_on=date(2999, 1, 1),
        rationale="authoritative upstream record demonstrates this package is not affected",
    )


def finding() -> dict:
    return {
        "name": "example-package",
        "version": "1.2.3",
        "vulns": [
            {
                "id": "PYSEC-2099-1",
                "aliases": ["CVE-2099-0001"],
                "fix_versions": ["1.2.4"],
            }
        ],
    }


def test_normalize_accepts_legacy_dependency_list() -> None:
    payload = [finding()]
    assert normalize_audit_payload(payload, service="pypi") == payload


def test_normalize_accepts_current_report_object() -> None:
    payload = {"dependencies": [finding()], "fixes": []}
    assert normalize_audit_payload(payload, service="pypi") == payload["dependencies"]


@pytest.mark.parametrize("payload", [{}, {"dependencies": {}}, "invalid", ["not-an-object"]])
def test_normalize_rejects_unknown_or_invalid_shapes(payload) -> None:
    with pytest.raises(RuntimeError):
        normalize_audit_payload(payload, service="pypi")


def test_vex_exception_is_exact_package_version_service_and_alias() -> None:
    dependencies = [finding()]
    assert evaluate("pypi", dependencies, [rule()]) == []
    assert evaluate("osv", dependencies, [rule()]) != []

    wrong_version = rule()
    wrong_version = ExceptionRule(
        vulnerability_id=wrong_version.vulnerability_id,
        package=wrong_version.package,
        version="9.9.9",
        services=wrong_version.services,
        expires_on=wrong_version.expires_on,
        rationale=wrong_version.rationale,
    )
    assert evaluate("pypi", dependencies, [wrong_version]) != []


def test_unexcepted_vulnerability_remains_blocking() -> None:
    unresolved = evaluate("pypi", [finding()], [])
    assert unresolved == [("example-package", "1.2.3", "PYSEC-2099-1", ["1.2.4"])]


def test_expired_vex_is_rejected(tmp_path) -> None:
    path = tmp_path / "vex.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "exceptions": [
                    {
                        "id": "CVE-2099-0001",
                        "package": "example-package",
                        "version": "1.2.3",
                        "services": ["pypi"],
                        "status": "not_affected",
                        "expires_on": "2000-01-01",
                        "rationale": "expired test rule",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expired VEX exception"):
        load_exceptions(path)


def test_vex_requires_complete_exact_scope(tmp_path) -> None:
    path = tmp_path / "vex.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "exceptions": [
                    {
                        "id": "CVE-2099-0001",
                        "package": "example-package",
                        "version": "1.2.3",
                        "services": ["unknown-service"],
                        "status": "not_affected",
                        "expires_on": "2999-01-01",
                        "rationale": "test",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid vulnerability service scope"):
        load_exceptions(path)
