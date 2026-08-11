from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
REQUIRED_FILES = (
    "index.html",
    "index.json",
    "robots.txt",
    "sitemap.xml",
    "CNAME",
    "favicon.svg",
    "site.webmanifest",
    ".well-known/security.txt",
)
FORBIDDEN_PUBLIC_MARKERS = (
    "example-claim-001",
    "example-claim-002",
    "example-source-001",
    "example-source-002",
    "example-entity-001",
    "example-entity-002",
    "Official Government Report",
    "John Smith",
)


class HeadAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang = ""
        self.html_dir = ""
        self.title_seen = False
        self.canonical_seen = False
        self.description_seen = False
        self.main_seen = False
        self.h1_count = 0
        self.json_ld_blocks: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang", "")
            self.html_dir = values.get("dir", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "link" and values.get("rel") == "canonical":
            self.canonical_seen = bool(values.get("href"))
        elif tag == "meta" and values.get("name") == "description":
            self.description_seen = bool(values.get("content"))
        elif tag == "main":
            self.main_seen = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "script" and values.get("type") == "application/ld+json":
            self._in_json_ld = True
            self._json_buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.title_seen = True
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self.json_ld_blocks.append("".join(self._json_buffer).strip())
            self._in_json_ld = False
            self._json_buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._json_buffer.append(data)


def validate_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        path = PUBLIC / relative
        if not path.is_file():
            errors.append(f"missing generated file: public/{relative}")


def validate_homepage(errors: list[str]) -> None:
    path = PUBLIC / "index.html"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    parser = HeadAuditParser()
    parser.feed(text)
    if parser.html_lang != "ar":
        errors.append(f"homepage lang must be ar, got {parser.html_lang!r}")
    if parser.html_dir != "rtl":
        errors.append(f"homepage dir must be rtl, got {parser.html_dir!r}")
    if not parser.title_seen:
        errors.append("homepage is missing a title")
    if not parser.description_seen:
        errors.append("homepage is missing a meta description")
    if not parser.canonical_seen:
        errors.append("homepage is missing a canonical URL")
    if not parser.main_seen:
        errors.append("homepage is missing a main landmark")
    if parser.h1_count != 1:
        errors.append(f"homepage must contain exactly one h1, got {parser.h1_count}")
    if not parser.json_ld_blocks:
        errors.append("homepage is missing JSON-LD")
    for index, block in enumerate(parser.json_ld_blocks, start=1):
        try:
            json.loads(block)
        except json.JSONDecodeError as exc:
            errors.append(f"homepage JSON-LD block {index} is invalid: {exc}")
    if "مرصد الذكاء الاصطناعي العربي" not in text:
        errors.append("homepage does not contain the approved Arabic brand name")


def validate_json_assets(errors: list[str]) -> None:
    for relative in ("index.json", "site.webmanifest"):
        path = PUBLIC / relative
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"public/{relative} is invalid JSON: {exc}")
            continue
        if relative == "index.json" and not isinstance(value, list):
            errors.append("public/index.json must contain a JSON array")
        if relative == "site.webmanifest" and not isinstance(value, dict):
            errors.append("public/site.webmanifest must contain a JSON object")


def validate_robots(errors: list[str]) -> None:
    path = PUBLIC / "robots.txt"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "Sitemap: https://aisearcharab.com/sitemap.xml" not in text:
        errors.append("robots.txt does not reference the canonical sitemap")
    if re.search(r"(?im)^\s*Disallow:\s*/\s*$", text):
        errors.append("robots.txt blocks the entire website")


def validate_no_fictional_production_data(errors: list[str]) -> None:
    for path in PUBLIC.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".json", ".xml", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in FORBIDDEN_PUBLIC_MARKERS:
            if marker in text:
                errors.append(f"fictional production marker {marker!r} found in {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    if not PUBLIC.is_dir():
        print("public directory does not exist; run Hugo first", file=sys.stderr)
        return 1
    validate_required_files(errors)
    validate_homepage(errors)
    validate_json_assets(errors)
    validate_robots(errors)
    validate_no_fictional_production_data(errors)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("✓ Generated site validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
