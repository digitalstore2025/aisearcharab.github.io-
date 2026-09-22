from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = Path(os.environ.get("PUBLIC_DIR", str(ROOT / "public"))).resolve()
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
AUTHOR_PROFILE = "authors/abdelrahman-jamal-abuasaker/index.html"
AUTHOR_ARTICLE = "investigations/methodology-demo/index.html"
AUTHOR_NAME = "Abdelrahman Jamal Abuasaker"
AUTHOR_NAME_AR = "عبد الرحمن جمال أبو عساكر"
AUTHOR_ALIASES = {
    "Abdelrahman J Abuasaker",
    "Abdelrahman Jamal Abu Asaker",
    "ABDELRAHMAN J A M A L AbuAsaker",
    AUTHOR_NAME_AR,
    "عبد الرحمن أبو عساكر",
}
AUTHOR_SAME_AS = {
    "https://www.linkedin.com/in/abdelrahman-j-abuasaker-a70ba4150/",
    "https://independent.academia.edu/abedjamal1",
}
AUTHOR_SUBJECT_OF = {
    "https://www.youtube.com/watch?v=JpiDVtyyi3M",
    "https://shms.ps/post/206827/%D8%AD%D9%86%D8%B8%D9%84%D8%A9-%D9%85%D8%B4%D8%B1%D9%88%D8%B9-PAL-AI-%D9%8A%D8%B7%D9%84%D9%82-%D9%86%D9%85%D9%88%D8%B0%D8%AC-%D8%A7-%D9%84%D8%BA%D9%88%D9%8A-%D8%A7-%D8%A8%D9%87%D9%88%D9%8A%D8%A9-%D9%81%D9%84%D8%B3%D8%B7%D9%8A%D9%86%D9%8A%D8%A9-%D8%AE%D8%A7%D9%84%D8%B5%D8%A9-%D9%84%D9%85%D9%88%D8%A7%D8%AC%D9%87%D8%A9-%D8%AA%D8%B2%D9%88%D9%8A%D8%B1-%D8%A7%D9%84%D8%B3%D8%B1%D8%AF%D9%8A%D8%A9",
}
SEARCH_CRAWLERS = ("Googlebot", "OAI-SearchBot", "PerplexityBot")


class HeadAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang = ""
        self.html_dir = ""
        self.title_seen = False
        self.canonical_seen = False
        self.canonical_href = ""
        self.description_seen = False
        self.robots_content = ""
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
            self.canonical_href = values.get("href", "")
            self.canonical_seen = bool(self.canonical_href)
        elif tag == "meta":
            if values.get("name") == "description":
                self.description_seen = bool(values.get("content"))
            elif values.get("name") == "robots":
                self.robots_content = values.get("content", "")
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


class InternalURLAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"href", "src", "action"} and value:
                self.urls.append((key, value))


def validate_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        path = PUBLIC / relative
        if not path.is_file():
            errors.append(f"missing generated file: {path}")


def homepage_document() -> tuple[HeadAuditParser, str] | None:
    path = PUBLIC / "index.html"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    parser = HeadAuditParser()
    parser.feed(text)
    return parser, text


def validate_homepage(errors: list[str]) -> None:
    document = homepage_document()
    if document is None:
        return
    parser, text = document
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


def validate_subpath_internal_urls(errors: list[str]) -> None:
    document = homepage_document()
    if document is None:
        return
    parser, _ = document
    if not parser.canonical_href:
        return
    base_path = urlparse(parser.canonical_href).path or "/"
    if not base_path.endswith("/"):
        base_path += "/"
    if base_path == "/":
        return
    for path in PUBLIC.rglob("*.html"):
        audit = InternalURLAuditParser()
        audit.feed(path.read_text(encoding="utf-8"))
        for attribute, value in audit.urls:
            if not value.startswith("/") or value.startswith("//"):
                continue
            if value == base_path.rstrip("/") or value.startswith(base_path):
                continue
            errors.append(
                f"subpath-breaking {attribute}={value!r} in {path.relative_to(ROOT)}; "
                f"deployment base is {base_path!r}"
            )


def validate_json_assets(errors: list[str]) -> None:
    for relative in ("index.json", "site.webmanifest"):
        path = PUBLIC / relative
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path} is invalid JSON: {exc}")
            continue
        if relative == "index.json":
            if not isinstance(value, list):
                errors.append(f"{path} must contain a JSON array")
            else:
                urls = {
                    item.get("url")
                    for item in value
                    if isinstance(item, dict) and isinstance(item.get("url"), str)
                }
                if not any(
                    url.rstrip("/").endswith("/authors/abdelrahman-jamal-abuasaker")
                    for url in urls
                ):
                    errors.append(f"{path} does not include the canonical author profile")
        if relative == "site.webmanifest" and not isinstance(value, dict):
            errors.append(f"{path} must contain a JSON object")


def validate_robots(errors: list[str]) -> None:
    path = PUBLIC / "robots.txt"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")

    document = homepage_document()
    if document is not None:
        parser, _ = document
        if parser.canonical_href:
            base_url = parser.canonical_href
            if not base_url.endswith("/"):
                base_url += "/"
            expected_sitemap = urljoin(base_url, "sitemap.xml")
            sitemap_values = {
                match.group(1).strip()
                for match in re.finditer(r"(?im)^\s*Sitemap:\s*(\S+)\s*$", text)
            }
            if expected_sitemap not in sitemap_values:
                errors.append(
                    "robots.txt sitemap does not match the generated canonical base: "
                    f"expected {expected_sitemap!r}, got {sorted(sitemap_values)!r}"
                )

    if re.search(r"(?im)^\s*Disallow:\s*/\s*$", text):
        errors.append("robots.txt blocks the entire website")
    for crawler in SEARCH_CRAWLERS:
        block = re.search(
            rf"(?ims)^\s*User-agent:\s*{re.escape(crawler)}\s*$"
            r"(.*?)(?=^\s*User-agent:|\Z)",
            text,
        )
        if block is None:
            errors.append(f"robots.txt has no explicit policy for {crawler}")
            continue
        if not re.search(r"(?im)^\s*Allow:\s*/\s*$", block.group(1)):
            errors.append(f"robots.txt does not allow / for {crawler}")


def parse_json_ld_document(
    relative: str, errors: list[str]
) -> tuple[HeadAuditParser, str, list[dict]] | None:
    path = PUBLIC / relative
    if not path.is_file():
        errors.append(f"missing generated page: {path}")
        return None
    text = path.read_text(encoding="utf-8")
    parser = HeadAuditParser()
    parser.feed(text)
    nodes: list[dict] = []
    if not parser.json_ld_blocks:
        errors.append(f"{relative} is missing JSON-LD")
    for index, block in enumerate(parser.json_ld_blocks, start=1):
        try:
            document = json.loads(block)
        except json.JSONDecodeError as exc:
            errors.append(f"{relative} JSON-LD block {index} is invalid: {exc}")
            continue
        if not isinstance(document, dict):
            errors.append(f"{relative} JSON-LD block {index} must be an object")
            continue
        graph = document.get("@graph")
        if graph is None:
            nodes.append(document)
        elif isinstance(graph, list) and all(isinstance(node, dict) for node in graph):
            nodes.extend(graph)
        else:
            errors.append(f"{relative} JSON-LD block {index} has an invalid @graph")
    return parser, text, nodes


def nodes_of_type(nodes: list[dict], schema_type: str) -> list[dict]:
    matches: list[dict] = []
    for node in nodes:
        value = node.get("@type")
        if value == schema_type or (isinstance(value, list) and schema_type in value):
            matches.append(node)
    return matches


def validate_author_entity(errors: list[str]) -> None:
    profile_document = parse_json_ld_document(AUTHOR_PROFILE, errors)
    if profile_document is None:
        return
    parser, text, nodes = profile_document
    if parser.html_lang != "ar" or parser.html_dir != "rtl":
        errors.append(f"{AUTHOR_PROFILE} must render as lang=ar and dir=rtl")
    if parser.h1_count != 1:
        errors.append(f"{AUTHOR_PROFILE} must contain exactly one h1, got {parser.h1_count}")
    if not parser.canonical_seen:
        errors.append(f"{AUTHOR_PROFILE} is missing a canonical URL")
    if "noindex" in parser.robots_content.lower():
        errors.append(f"{AUTHOR_PROFILE} must be indexable")
    for name in (AUTHOR_NAME, AUTHOR_NAME_AR):
        if name not in text:
            errors.append(f"{AUTHOR_PROFILE} does not visibly contain {name!r}")

    people = nodes_of_type(nodes, "Person")
    profiles = nodes_of_type(nodes, "ProfilePage")
    if len(people) != 1:
        errors.append(f"{AUTHOR_PROFILE} must contain one Person node, got {len(people)}")
        return
    if len(profiles) != 1:
        errors.append(f"{AUTHOR_PROFILE} must contain one ProfilePage node, got {len(profiles)}")
        return

    person = people[0]
    profile = profiles[0]
    person_id = f"{parser.canonical_href}#person"
    if person.get("@id") != person_id:
        errors.append(f"Person @id must be {person_id!r}, got {person.get('@id')!r}")
    if person.get("name") != AUTHOR_NAME:
        errors.append(f"Person name must be {AUTHOR_NAME!r}")
    aliases = person.get("alternateName")
    if not isinstance(aliases, list) or not AUTHOR_ALIASES.issubset(set(aliases)):
        errors.append("Person alternateName does not contain every approved alias")
    same_as = person.get("sameAs")
    if not isinstance(same_as, list) or set(same_as) != AUTHOR_SAME_AS:
        errors.append("Person sameAs does not match the approved identity profiles")
    subject_of = person.get("subjectOf")
    if not isinstance(subject_of, list):
        errors.append("Person subjectOf must be a list")
    else:
        subject_urls = {
            item.get("url") for item in subject_of if isinstance(item, dict) and item.get("url")
        }
        if subject_urls != AUTHOR_SUBJECT_OF:
            errors.append("Person subjectOf does not match the registered media sources")
    main_entity = profile.get("mainEntity")
    if not isinstance(main_entity, dict) or main_entity.get("@id") != person_id:
        errors.append("ProfilePage.mainEntity does not reference the canonical Person @id")

    article_document = parse_json_ld_document(AUTHOR_ARTICLE, errors)
    if article_document is None:
        return
    _, _, article_nodes = article_document
    articles = nodes_of_type(article_nodes, "Article")
    if len(articles) != 1:
        errors.append(f"{AUTHOR_ARTICLE} must contain one Article node, got {len(articles)}")
        return
    article = articles[0]
    authors = article.get("author")
    if isinstance(authors, dict):
        authors = [authors]
    if not isinstance(authors, list):
        errors.append(f"{AUTHOR_ARTICLE} Article.author must be a list")
        return
    matching_authors = [
        author
        for author in authors
        if isinstance(author, dict) and author.get("@id") == person_id
    ]
    if len(matching_authors) != 1:
        errors.append(f"{AUTHOR_ARTICLE} must reference the canonical Person exactly once")
    elif matching_authors[0].get("@type") != "Person":
        errors.append(f"{AUTHOR_ARTICLE} canonical author must use @type Person")
    home = homepage_document()
    if home is not None:
        home_parser, _ = home
        expected_publisher_id = f"{home_parser.canonical_href}#organization"
        publisher = article.get("publisher")
        if not isinstance(publisher, dict) or publisher.get("@id") != expected_publisher_id:
            errors.append(f"{AUTHOR_ARTICLE} publisher must reference {expected_publisher_id!r}")


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
        print(f"generated directory does not exist: {PUBLIC}", file=sys.stderr)
        return 1
    validate_required_files(errors)
    validate_homepage(errors)
    validate_subpath_internal_urls(errors)
    validate_json_assets(errors)
    validate_robots(errors)
    validate_author_entity(errors)
    validate_no_fictional_production_data(errors)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"✓ Generated site validation passed: {PUBLIC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
