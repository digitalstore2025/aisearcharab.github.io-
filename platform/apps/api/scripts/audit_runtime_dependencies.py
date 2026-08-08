from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExceptionRule:
    vulnerability_id: str
    package: str
    version: str
    services: frozenset[str]
    expires_on: date
    rationale: str


def load_exceptions(path: Path) -> list[ExceptionRule]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != 1 or not isinstance(payload.get("exceptions"), list):
        raise ValueError("unsupported VEX exception schema")

    rules: list[ExceptionRule] = []
    today = date.today()
    for entry in payload["exceptions"]:
        if not isinstance(entry, dict):
            raise ValueError("VEX exception entries must be objects")
        if entry.get("status") != "not_affected":
            raise ValueError("only not_affected VEX exceptions are permitted")
        expiry = date.fromisoformat(str(entry["expires_on"]))
        if expiry < today:
            raise ValueError(f"expired VEX exception: {entry['id']} ({expiry.isoformat()})")
        services = frozenset(str(item).lower() for item in entry.get("services", []))
        if not services or not services.issubset({"pypi", "osv"}):
            raise ValueError(f"invalid vulnerability service scope for {entry['id']}")
        package = str(entry.get("package", "")).strip().lower()
        version = str(entry.get("version", "")).strip()
        vulnerability_id = str(entry.get("id", "")).strip()
        rationale = str(entry.get("rationale", "")).strip()
        if not package or not version or not vulnerability_id or not rationale:
            raise ValueError("VEX exceptions require id, package, version and rationale")
        rules.append(
            ExceptionRule(
                vulnerability_id=vulnerability_id,
                package=package,
                version=version,
                services=services,
                expires_on=expiry,
                rationale=rationale,
            )
        )
    return rules


def normalize_audit_payload(payload: Any, *, service: str) -> list[dict]:
    """Return dependency records from supported pip-audit JSON shapes.

    pip-audit has emitted both a legacy top-level dependency list and a report
    object containing a ``dependencies`` array. Supporting only these explicit
    shapes keeps the gate fail-closed if the upstream schema changes again.
    """
    if isinstance(payload, list):
        dependencies = payload
    elif isinstance(payload, dict) and isinstance(payload.get("dependencies"), list):
        dependencies = payload["dependencies"]
    else:
        raise RuntimeError(f"unexpected pip-audit JSON shape for service={service}")

    if any(not isinstance(item, dict) for item in dependencies):
        raise RuntimeError(f"invalid dependency record in pip-audit JSON for service={service}")
    return dependencies


def run_audit(lock: Path, service: str) -> list[dict]:
    command = [
        sys.executable,
        "-m",
        "pip_audit",
        "-r",
        str(lock),
        "--require-hashes",
        "--strict",
        "--progress-spinner",
        "off",
        "--format",
        "json",
        "--desc",
        "off",
        "--aliases",
        "on",
        "--vulnerability-service",
        service,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        sys.stderr.write(completed.stderr)
        raise RuntimeError(f"pip-audit collection failed for service={service} exit={completed.returncode}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(completed.stderr)
        raise RuntimeError(f"pip-audit emitted invalid JSON for service={service}") from exc
    return normalize_audit_payload(payload, service=service)


def finding_ids(vulnerability: dict) -> set[str]:
    identifiers = {str(vulnerability.get("id", "")).strip()}
    identifiers.update(str(alias).strip() for alias in vulnerability.get("aliases", []) or [])
    return {identifier for identifier in identifiers if identifier}


def evaluate(service: str, dependencies: list[dict], rules: list[ExceptionRule]) -> list[tuple[str, str, str, list[str]]]:
    unresolved: list[tuple[str, str, str, list[str]]] = []
    for dependency in dependencies:
        package = str(dependency.get("name", "")).lower()
        version = str(dependency.get("version", ""))
        vulnerabilities = dependency.get("vulns", []) or []
        if not isinstance(vulnerabilities, list):
            raise RuntimeError(f"invalid vulnerability list for package={package or 'unknown'} service={service}")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise RuntimeError(f"invalid vulnerability record for package={package or 'unknown'} service={service}")
            ids = finding_ids(vulnerability)
            matched = next(
                (
                    rule
                    for rule in rules
                    if service in rule.services
                    and rule.package == package
                    and rule.version == version
                    and rule.vulnerability_id in ids
                ),
                None,
            )
            if matched is not None:
                print(
                    "vex_not_affected="
                    f"{matched.vulnerability_id} package={package} version={version} "
                    f"service={service} expires={matched.expires_on.isoformat()}"
                )
                continue
            primary = str(vulnerability.get("id", "unknown"))
            fixes = [str(item) for item in vulnerability.get("fix_versions", []) or []]
            unresolved.append((package, version, primary, fixes))
    return unresolved


def write_report(
    report_dir: Path,
    *,
    service: str,
    dependencies: list[dict],
    unresolved: list[tuple[str, str, str, list[str]]],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "service": service,
        "dependencies": dependencies,
        "unresolved": [
            {"package": package, "version": version, "id": vulnerability_id, "fix_versions": fixes}
            for package, version, vulnerability_id, fixes in unresolved
        ],
    }
    (report_dir / f"{service}.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a hashed runtime lock against PyPI and OSV with expiring VEX rules.")
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--vex", required=True, type=Path)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()

    rules = load_exceptions(args.vex)
    all_unresolved: list[tuple[str, str, str, list[str], str]] = []
    for service in ("pypi", "osv"):
        dependencies = run_audit(args.lock, service)
        unresolved = evaluate(service, dependencies, rules)
        if args.report_dir is not None:
            write_report(args.report_dir, service=service, dependencies=dependencies, unresolved=unresolved)
        all_unresolved.extend((*item, service) for item in unresolved)

    if all_unresolved:
        print("unresolved_dependency_vulnerabilities:", file=sys.stderr)
        for package, version, vulnerability_id, fixes, service in all_unresolved:
            print(
                f"- service={service} package={package} version={version} id={vulnerability_id} fixes={','.join(fixes) or 'none'}",
                file=sys.stderr,
            )
        return 1

    print("dependency_audit=pass services=pypi,osv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
