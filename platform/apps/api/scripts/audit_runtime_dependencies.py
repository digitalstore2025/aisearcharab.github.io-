from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


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
    if payload.get("schema") != 1 or not isinstance(payload.get("exceptions"), list):
        raise ValueError("unsupported VEX exception schema")

    rules: list[ExceptionRule] = []
    today = date.today()
    for entry in payload["exceptions"]:
        if entry.get("status") != "not_affected":
            raise ValueError("only not_affected VEX exceptions are permitted")
        expiry = date.fromisoformat(entry["expires_on"])
        if expiry < today:
            raise ValueError(f"expired VEX exception: {entry['id']} ({expiry.isoformat()})")
        services = frozenset(entry.get("services", []))
        if not services or not services.issubset({"pypi", "osv"}):
            raise ValueError(f"invalid vulnerability service scope for {entry['id']}")
        rules.append(
            ExceptionRule(
                vulnerability_id=entry["id"],
                package=entry["package"].lower(),
                version=entry["version"],
                services=services,
                expires_on=expiry,
                rationale=entry["rationale"],
            )
        )
    return rules


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
    if not isinstance(payload, list):
        raise RuntimeError(f"unexpected pip-audit JSON shape for service={service}")
    return payload


def finding_ids(vulnerability: dict) -> set[str]:
    identifiers = {str(vulnerability.get("id", "")).strip()}
    identifiers.update(str(alias).strip() for alias in vulnerability.get("aliases", []) or [])
    return {identifier for identifier in identifiers if identifier}


def evaluate(service: str, dependencies: list[dict], rules: list[ExceptionRule]) -> list[tuple[str, str, str, list[str]]]:
    unresolved: list[tuple[str, str, str, list[str]]] = []
    for dependency in dependencies:
        package = str(dependency.get("name", "")).lower()
        version = str(dependency.get("version", ""))
        for vulnerability in dependency.get("vulns", []) or []:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a hashed runtime lock against PyPI and OSV with expiring VEX rules.")
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--vex", required=True, type=Path)
    args = parser.parse_args()

    rules = load_exceptions(args.vex)
    all_unresolved: list[tuple[str, str, str, list[str], str]] = []
    for service in ("pypi", "osv"):
        dependencies = run_audit(args.lock, service)
        unresolved = evaluate(service, dependencies, rules)
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
