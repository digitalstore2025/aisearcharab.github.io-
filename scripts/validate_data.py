from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CONFIDENCE_VALUES = {"high", "medium", "low", "unverified"}
RELIABILITY_VALUES = {"primary", "secondary", "tertiary", "unverified"}
CLAIM_TYPES = {"verified-fact", "estimate", "inference", "third-party-claim"}
REVIEW_STATUSES = {"draft", "reviewed", "published", "rejected"}
ENTITY_TYPES = {"person", "organization", "company", "government", "location", "project", "other"}
ENTITY_STATUSES = {"active", "inactive", "unknown"}
SOURCE_TYPES = {
    "official-document",
    "dataset",
    "webpage",
    "social-post",
    "interview",
    "media-report",
    "academic-paper",
    "legal-record",
    "other",
}

SOURCE_REQUIRED = {"id", "title", "publisher", "url", "accessed_at", "source_type", "language", "reliability"}
CLAIM_REQUIRED = {"id", "text", "claim_type", "confidence", "sources", "review_status", "verified_at"}
ENTITY_REQUIRED = {"id", "name", "entity_type", "status", "aliases"}


def load_json(path: Path) -> tuple[dict, list[str]]:
    """Load and parse JSON file with error handling."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"{path}: invalid JSON: {exc}"]
    if not isinstance(value, dict):
        return {}, [f"{path}: root must be an object"]
    return value, []


def validate_iso8601_datetime(date_str: str) -> bool:
    """Validate ISO 8601 datetime format."""
    try:
        datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def validate_id_format(record_id: str) -> bool:
    """Validate kebab-case ID format."""
    return isinstance(record_id, str) and ID_PATTERN.fullmatch(record_id) is not None


def validate_uri(uri: str) -> bool:
    """Validate URI format."""
    try:
        parsed = urlparse(str(uri))
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def validate_language_code(lang: str) -> bool:
    """Validate ISO 639-1 language code."""
    pattern = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
    return isinstance(lang, str) and pattern.fullmatch(lang) is not None


def common_checks(path: Path, data: dict, required: set[str]) -> list[str]:
    """Perform common validation checks for all record types."""
    errors: list[str] = []
    
    # Check for missing required fields
    missing = sorted(required - data.keys())
    if missing:
        errors.append(f"{path}: missing required fields {missing}")
    
    # Check ID format and match filename
    record_id = data.get("id")
    if record_id != path.stem:
        errors.append(f"{path}: id '{record_id}' must match filename '{path.stem}'")
    if not validate_id_format(record_id):
        errors.append(f"{path}: invalid id format '{record_id}' (must be kebab-case)")
    
    return errors


def validate_source(path: Path, source_ids: set[str]) -> list[str]:
    """Validate source record."""
    data, errors = load_json(path)
    if errors:
        return errors
    
    errors += common_checks(path, data, SOURCE_REQUIRED)
    
    # Validate URL
    url = data.get("url", "")
    if not validate_uri(url):
        errors.append(f"{path}: url must be a valid HTTP(S) URI, got '{url}'")
    
    # Validate language code
    language = data.get("language", "")
    if not validate_language_code(language):
        errors.append(f"{path}: language code must be ISO 639-1 format (e.g., 'ar', 'en', 'ar-SA'), got '{language}'")
    
    # Validate reliability
    reliability = data.get("reliability")
    if reliability not in RELIABILITY_VALUES:
        errors.append(f"{path}: reliability must be one of {sorted(RELIABILITY_VALUES)}, got '{reliability}'")
    
    # Validate source_type
    source_type = data.get("source_type")
    if source_type not in SOURCE_TYPES:
        errors.append(f"{path}: source_type must be one of {sorted(SOURCE_TYPES)}, got '{source_type}'")
    
    # Validate accessed_at datetime
    accessed_at = data.get("accessed_at")
    if not validate_iso8601_datetime(accessed_at):
        errors.append(f"{path}: accessed_at must be valid ISO 8601 datetime, got '{accessed_at}'")
    
    # Validate published_at if present
    published_at = data.get("published_at")
    if published_at is not None and not validate_iso8601_datetime(published_at):
        errors.append(f"{path}: published_at must be valid ISO 8601 datetime, got '{published_at}'")
    
    # Validate archive_url if present
    archive_url = data.get("archive_url")
    if archive_url is not None and not validate_uri(archive_url):
        errors.append(f"{path}: archive_url must be valid HTTP(S) URI, got '{archive_url}'")
    
    # Check integrity hash if present
    integrity = data.get("integrity", {})
    if integrity and isinstance(integrity, dict):
        sha256 = integrity.get("sha256")
        if sha256 and not re.match(r"^[a-f0-9]{64}$", sha256):
            errors.append(f"{path}: integrity.sha256 must be valid SHA-256 hex, got '{sha256}'")
    
    source_ids.add(str(data.get("id", "")))
    return errors


def validate_claim(path: Path, source_ids: set[str]) -> list[str]:
    """Validate claim record."""
    data, errors = load_json(path)
    if errors:
        return errors
    
    errors += common_checks(path, data, CLAIM_REQUIRED)
    
    # Validate claim_type
    claim_type = data.get("claim_type")
    if claim_type not in CLAIM_TYPES:
        errors.append(f"{path}: claim_type must be one of {sorted(CLAIM_TYPES)}, got '{claim_type}'")
    
    # Validate confidence
    confidence = data.get("confidence")
    if confidence not in CONFIDENCE_VALUES:
        errors.append(f"{path}: confidence must be one of {sorted(CONFIDENCE_VALUES)}, got '{confidence}'")
    
    # Validate review_status
    review_status = data.get("review_status")
    if review_status not in REVIEW_STATUSES:
        errors.append(f"{path}: review_status must be one of {sorted(REVIEW_STATUSES)}, got '{review_status}'")
    
    # Validate verified_at datetime
    verified_at = data.get("verified_at")
    if not validate_iso8601_datetime(verified_at):
        errors.append(f"{path}: verified_at must be valid ISO 8601 datetime, got '{verified_at}'")
    
    # Validate sources reference existing sources
    references = data.get("sources", [])
    if not isinstance(references, list) or not references:
        errors.append(f"{path}: sources must be a non-empty list")
    else:
        unknown = sorted(set(references) - source_ids)
        if unknown:
            errors.append(f"{path}: unknown source ids {unknown} (sources must exist in data/sources/)")
        # Check for duplicate source references
        if len(references) != len(set(references)):
            duplicates = [src for src in set(references) if references.count(src) > 1]
            errors.append(f"{path}: duplicate source references {duplicates}")
    
    # Validate text length
    text = data.get("text", "")
    if len(text) < 10:
        errors.append(f"{path}: text must be at least 10 characters, got {len(text)}")
    
    return errors


def validate_entity(path: Path, source_ids: set[str]) -> list[str]:
    """Validate entity record."""
    data, errors = load_json(path)
    if errors:
        return errors
    
    errors += common_checks(path, data, ENTITY_REQUIRED)
    
    # Validate entity_type
    entity_type = data.get("entity_type")
    if entity_type not in ENTITY_TYPES:
        errors.append(f"{path}: entity_type must be one of {sorted(ENTITY_TYPES)}, got '{entity_type}'")
    
    # Validate status
    status = data.get("status")
    if status not in ENTITY_STATUSES:
        errors.append(f"{path}: status must be one of {sorted(ENTITY_STATUSES)}, got '{status}'")
    
    # Validate aliases
    aliases = data.get("aliases", [])
    if not isinstance(aliases, list):
        errors.append(f"{path}: aliases must be a list")
    elif not aliases:
        errors.append(f"{path}: aliases must contain at least one entry (can be empty string or duplicate name)")
    else:
        # Check for empty string aliases
        empty_aliases = [i for i, alias in enumerate(aliases) if not isinstance(alias, str) or len(alias) == 0]
        if empty_aliases:
            errors.append(f"{path}: aliases cannot contain empty strings at indices {empty_aliases}")
    
    # Validate source_ids reference if present
    source_references = data.get("source_ids", [])
    if source_references is not None:
        if not isinstance(source_references, list):
            errors.append(f"{path}: source_ids must be a list")
        else:
            unknown = sorted(set(source_references) - source_ids)
            if unknown:
                errors.append(f"{path}: unknown source ids {unknown} (sources must exist in data/sources/)")
    
    return errors


def run() -> list[str]:
    """Run all validation checks."""
    errors: list[str] = []
    source_ids: set[str] = set()
    
    # Validate sources first (others depend on them)
    sources_dir = ROOT / "data" / "sources"
    if sources_dir.exists():
        for path in sorted(sources_dir.glob("*.json")):
            errors += validate_source(path, source_ids)
    
    # Validate claims
    claims_dir = ROOT / "data" / "claims"
    if claims_dir.exists():
        for path in sorted(claims_dir.glob("*.json")):
            errors += validate_claim(path, source_ids)
    
    # Validate entities
    entities_dir = ROOT / "data" / "entities"
    if entities_dir.exists():
        for path in sorted(entities_dir.glob("*.json")):
            errors += validate_entity(path, source_ids)
    
    return errors


def main() -> int:
    """Main entry point."""
    errors = run()
    if errors:
        print("\n".join(errors))
        return 1
    print("✓ Structured data validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
