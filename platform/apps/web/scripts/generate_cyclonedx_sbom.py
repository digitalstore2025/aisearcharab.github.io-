#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

DEPENDENCY_BUCKETS = ("dependencies", "devDependencies", "optionalDependencies")
VERSION_PREFIX = re.compile(r"^(?:npm:)?(.+?)(?:\([^)]*\))*$")


def fail(message: str) -> None:
    raise SystemExit(f"SBOM GENERATION FAILED: {message}")


def normalize_version(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    match = VERSION_PREFIX.match(raw)
    version = match.group(1) if match else raw
    if version.startswith("link:") or version.startswith("workspace:") or version.startswith("file:"):
        return None
    return version


def npm_purl(name: str, version: str) -> str:
    return f"pkg:npm/{quote(name, safe='/')}@{quote(version, safe='.-_~')}"


def collect_components(node: object, discovered: dict[str, dict[str, str]], inherited_name: str | None = None) -> None:
    if not isinstance(node, dict):
        return

    name = node.get("name") if isinstance(node.get("name"), str) else inherited_name
    version = normalize_version(node.get("version"))
    if name and version and name != "@aisearcharab/web":
        purl = npm_purl(name, version)
        discovered[purl] = {
            "type": "library",
            "name": name,
            "version": version,
            "purl": purl,
            "bom-ref": purl,
        }

    for bucket in DEPENDENCY_BUCKETS:
        dependencies = node.get(bucket)
        if not isinstance(dependencies, dict):
            continue
        for dep_name, dep_node in dependencies.items():
            if isinstance(dep_name, str):
                collect_components(dep_node, discovered, dep_name)


def load_graph(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read pnpm JSON graph: {exc}")
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload or not all(isinstance(item, dict) for item in payload):
        fail("pnpm list output must be a non-empty JSON object/array")
    return payload


def build_bom(graph: list[dict[str, Any]], scope: str) -> dict[str, object]:
    discovered: dict[str, dict[str, str]] = {}
    for root in graph:
        collect_components(root, discovered)

    if not discovered:
        fail("dependency graph produced zero components")

    components = [discovered[key] for key in sorted(discovered)]
    fingerprint = "\n".join(item["bom-ref"] for item in components)
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"https://aisearcharab.com/sbom/{scope}\n{fingerprint}")

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "@aisearcharab/web",
                "version": "0.1.0",
            },
            "properties": [
                {"name": "aisearcharab:dependency-scope", "value": scope},
                {"name": "aisearcharab:generator", "value": "pnpm-list+python"},
            ],
        },
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic CycloneDX SBOM from pnpm list JSON.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scope", required=True, choices=("runtime", "build"))
    args = parser.parse_args()

    bom = build_bom(load_graph(args.input), args.scope)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bom, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"cyclonedx_sbom={args.output} scope={args.scope} components={len(bom['components'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
