from __future__ import annotations

import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

PUBLIC = Path(os.environ.get("PUBLIC_DIR", "public")).resolve()
REQUIRED = ("llms.txt", "ai-search-readiness.json")
EXPECTED_ORIGIN = "https://aisearcharab.com/"
EXPECTED_DISCOVERY = {
    "robots": "https://aisearcharab.com/robots.txt",
    "sitemap": "https://aisearcharab.com/sitemap.xml",
    "rss": "https://aisearcharab.com/index.xml",
    "search_index": "https://aisearcharab.com/index.json",
    "llms_txt": "https://aisearcharab.com/llms.txt",
}
REQUIRED_EVIDENCE = [
    "implementation",
    "ci",
    "merge",
    "deployment",
    "runtime_verification",
    "production_readiness",
]


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        self.links.append({key.lower(): value or "" for key, value in attrs})


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def is_exact_https_url(value: object, expected: str) -> bool:
    if not isinstance(value, str) or value != expected:
        return False
    parsed = urlparse(value)
    origin = urlparse(EXPECTED_ORIGIN)
    return parsed.scheme == "https" and parsed.netloc == origin.netloc and not parsed.query and not parsed.fragment


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
                    missing = set(EXPECTED_DISCOVERY) - set(discovery)
                    extra = set(discovery) - set(EXPECTED_DISCOVERY)
                    if missing:
                        fail(f"discovery missing keys: {sorted(missing)}", errors)
                    if extra:
                        fail(f"discovery has unexpected keys: {sorted(extra)}", errors)
                    for key, expected in EXPECTED_DISCOVERY.items():
                        if key in discovery and not is_exact_https_url(discovery[key], expected):
                            fail(f"discovery.{key} must equal {expected}", errors)
                if data.get("evidence_model") != REQUIRED_EVIDENCE:
                    fail("evidence_model must preserve the ordered release-evidence ladder", errors)

    homepage = PUBLIC / "index.html"
    if not homepage.is_file():
        fail("missing homepage for AI Search link validation", errors)
    else:
        parser = LinkCollector()
        parser.feed(homepage.read_text(encoding="utf-8"))
        describedby = [link for link in parser.links if "describedby" in link.get("rel", "").lower().split()]
        expected_href = EXPECTED_DISCOVERY["llms_txt"]
        if not any(link.get("href") == expected_href and link.get("type", "").lower() == "text/markdown" for link in describedby):
            fail(f"homepage must advertise {expected_href} via rel=describedby type=text/markdown", errors)

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("✓ AI Search discovery/readiness surfaces validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
