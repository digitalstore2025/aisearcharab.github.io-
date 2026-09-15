from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

PUBLIC = Path(os.environ.get("PUBLIC_DIR", "public")).resolve()
REQUIRED = ("llms.txt", "ai-search-readiness.json")
EXPECTED_ORIGIN = "https://aisearcharab.com/"
REQUIRED_DISCOVERY_KEYS = {"robots", "sitemap", "rss", "search_index", "llms_txt"}
REQUIRED_EVIDENCE = [
    "implementation",
    "ci",
    "merge",
    "deployment",
    "runtime_verification",
    "production_readiness",
]


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def valid_https_under_origin(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    origin = urlparse(EXPECTED_ORIGIN)
    return parsed.scheme == "https" and parsed.netloc == origin.netloc and bool(parsed.path)


def main() -> int:
    errors: list[str] = []
    for name in REQUIRED:
        if not (PUBLIC / name).is_file():
            fail(f"missing required AI Search surface: {name}", errors)

    llms = PUBLIC / "llms.txt"
    if llms.is_file():
        text = llms.read_text(encoding="utf-8").strip()
        if len(text) < 200:
            fail("llms.txt is unexpectedly small", errors)
        for required in ("# AI Search Arab", EXPECTED_ORIGIN, "/methodology/", "/corrections/"):
            if required not in text:
                fail(f"llms.txt missing required marker: {required}", errors)

    readiness = PUBLIC / "ai-search-readiness.json"
    if readiness.is_file():
        try:
            data = json.loads(readiness.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"ai-search-readiness.json invalid JSON: {exc}", errors)
        else:
            if not isinstance(data, dict):
                fail("ai-search-readiness.json must be an object", errors)
            else:
                if data.get("canonical_origin") != EXPECTED_ORIGIN:
                    fail("canonical_origin must match the approved canonical origin", errors)
                if data.get("language") != "ar":
                    fail("language must be ar", errors)
                if data.get("production_readiness_claim") is not False:
                    fail("production_readiness_claim must remain false until external gates are proven", errors)
                discovery = data.get("discovery")
                if not isinstance(discovery, dict):
                    fail("discovery must be an object", errors)
                else:
                    missing = REQUIRED_DISCOVERY_KEYS - set(discovery)
                    if missing:
                        fail(f"discovery missing keys: {sorted(missing)}", errors)
                    for key in REQUIRED_DISCOVERY_KEYS & set(discovery):
                        if not valid_https_under_origin(discovery[key]):
                            fail(f"discovery.{key} must be an HTTPS canonical-origin URL", errors)
                if data.get("evidence_model") != REQUIRED_EVIDENCE:
                    fail("evidence_model must preserve the ordered release-evidence ladder", errors)

    homepage = PUBLIC / "index.html"
    if homepage.is_file():
        html = homepage.read_text(encoding="utf-8")
        if 'rel="describedby"' not in html or "llms.txt" not in html:
            fail("homepage must advertise llms.txt via rel=describedby", errors)

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("✓ AI Search discovery/readiness surfaces validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
