from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_REQUIRED = {"id", "title", "publisher", "url", "accessed_at", "source_type", "language", "reliability"}
CLAIM_REQUIRED = {"id", "text", "claim_type", "confidence", "sources", "review_status", "verified_at"}
ENTITY_REQUIRED = {"id", "name", "entity_type", "status", "aliases"}


def load_json(path: Path) -> tuple[dict, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"{path}: invalid JSON: {exc}"]
    if not isinstance(value, dict):
        return {}, [f"{path}: root must be an object"]
    return value, []


def common_checks(path: Path, data: dict, required: set[str]) -> list[str]:
    errors: list[str] = []
    missing = sorted(required - data.keys())
    if missing:
        errors.append(f"{path}: missing fields {missing}")
    record_id = data.get("id")
    if record_id != path.stem:
        errors.append(f"{path}: id must match filename")
    if not isinstance(record_id, str) or not ID_PATTERN.fullmatch(record_id):
        errors.append(f"{path}: invalid id format")
    return errors


def validate_source(path: Path, source_ids: set[str]) -> list[str]:
    data, errors = load_json(path)
    if errors:
        return errors
    errors += common_checks(path, data, SOURCE_REQUIRED)
    parsed = urlparse(str(data.get("url", "")))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{path}: url must be an absolute HTTP(S) URL")
    source_ids.add(str(data.get("id", "")))
    return errors


def validate_claim(path: Path, source_ids: set[str]) -> list[str]:
    data, errors = load_json(path)
    if errors:
        return errors
    errors += common_checks(path, data, CLAIM_REQUIRED)
    references = data.get("sources", [])
    if not isinstance(references, list) or not references:
        errors.append(f"{path}: sources must be a non-empty list")
    else:
        unknown = sorted(set(references) - source_ids)
        if unknown:
            errors.append(f"{path}: unknown source ids {unknown}")
    return errors


def validate_entity(path: Path, source_ids: set[str]) -> list[str]:
    data, errors = load_json(path)
    if errors:
        return errors
    errors += common_checks(path, data, ENTITY_REQUIRED)
    references = data.get("source_ids", [])
    if not isinstance(references, list):
        errors.append(f"{path}: source_ids must be a list")
    else:
        unknown = sorted(set(references) - source_ids)
        if unknown:
            errors.append(f"{path}: unknown source ids {unknown}")
    return errors


def run() -> list[str]:
    errors: list[str] = []
    source_ids: set[str] = set()
    for path in sorted((ROOT / "data" / "sources").glob("*.json")):
        errors += validate_source(path, source_ids)
    for path in sorted((ROOT / "data" / "claims").glob("*.json")):
        errors += validate_claim(path, source_ids)
    for path in sorted((ROOT / "data" / "entities").glob("*.json")):
        errors += validate_entity(path, source_ids)
    return errors


def main() -> int:
    errors = run()
    if errors:
        print("\n".join(errors))
        return 1
    print("Structured data validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
