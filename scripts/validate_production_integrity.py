from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.net", "example-gov.org"}
PLACEHOLDER_TOKENS = {"john smith", "example organization", "official government report"}


def load_records() -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for path in sorted(DATA.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue  # validate_data.py reports syntax failures.
        if isinstance(value, dict):
            records.append((path, value))
    return records


def main() -> int:
    errors: list[str] = []
    for path, record in load_records():
        record_id = str(record.get("id", "")).lower()
        review_status = str(record.get("review_status", "")).lower()
        text = " ".join(
            str(record.get(field, ""))
            for field in ("title", "name", "text", "description", "publisher", "notes")
        ).lower()

        is_fixture_id = record_id.startswith(("sample-", "example-", "test-", "fixture-"))
        if is_fixture_id and review_status == "published":
            errors.append(f"{path.relative_to(ROOT)}: fixture-like record cannot be published")

        for token in PLACEHOLDER_TOKENS:
            if token in text and review_status in {"published", "reviewed"}:
                errors.append(f"{path.relative_to(ROOT)}: placeholder token {token!r} in reviewable production record")

        url = record.get("url")
        if isinstance(url, str) and url:
            host = (urlparse(url).hostname or "").lower()
            if host in PLACEHOLDER_HOSTS and review_status in {"published", "reviewed"}:
                errors.append(f"{path.relative_to(ROOT)}: placeholder URL host {host!r} is not valid production evidence")

        if review_status == "published":
            notes = str(record.get("notes", "")).lower()
            if any(marker in notes for marker in ("template", "replace before", "testing", "تجريبي", "استبداله")):
                errors.append(f"{path.relative_to(ROOT)}: published record is explicitly marked as a template or test")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("✓ Production data integrity validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
