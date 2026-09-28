from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "digitalstore2025/aisearcharab.github.io-")
EXPECTED_ORIGIN = os.environ.get("PAGES_EXPECTED_CANONICAL_ORIGIN", "https://aisearcharab.com/")
EXPECTED_BUILD_TYPE = os.environ.get("PAGES_EXPECTED_BUILD_TYPE", "workflow")
SETTLE_SECONDS = int(os.environ.get("PAGES_RUNTIME_SETTLE_SECONDS", "30"))
TIMEOUT_SECONDS = float(os.environ.get("PAGES_RUNTIME_TIMEOUT_SECONDS", "15"))

EXPECTED_HOST = urlparse(EXPECTED_ORIGIN).hostname or ""
EXPECTED_LLMS = f"{EXPECTED_ORIGIN.rstrip('/')}/llms.txt"
PAGES_API = f"https://api.github.com/repos/{REPOSITORY}/pages"


class HeadLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonical: list[str] = []
        self.describedby: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        rel_tokens = {token.lower() for token in values.get("rel", "").split()}
        if "canonical" in rel_tokens and values.get("href"):
            self.canonical.append(values["href"])
        if "describedby" in rel_tokens and values.get("href"):
            self.describedby.append((values["href"], values.get("type", "").lower()))


def request(url: str, *, accept: str | None = None) -> tuple[int, str, str, str]:
    headers = {
        "User-Agent": "aisearcharab-pages-runtime-validator/1.0",
        "Accept": accept or "*/*",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2026-03-10"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8", "replace")
        return response.status, response.geturl(), response.headers.get("content-type", ""), body


def validate_pages_configuration(errors: list[str]) -> None:
    try:
        status, _, _, body = request(PAGES_API, accept="application/vnd.github+json")
    except urllib.error.HTTPError as exc:
        errors.append(f"GitHub Pages API returned HTTP {exc.code} for {PAGES_API}")
        return
    except Exception as exc:  # network failures are release evidence failures
        errors.append(f"GitHub Pages API request failed: {exc}")
        return

    if status != 200:
        errors.append(f"GitHub Pages API returned unexpected HTTP {status}")
        return

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        errors.append(f"GitHub Pages API returned invalid JSON: {exc}")
        return

    build_type = data.get("build_type")
    if build_type != EXPECTED_BUILD_TYPE:
        errors.append(
            f"GitHub Pages build_type must be {EXPECTED_BUILD_TYPE!r}, got {build_type!r}; "
            "legacy branch builds can overwrite the validated Hugo deployment"
        )

    cname = (data.get("cname") or "").rstrip(".").lower()
    if EXPECTED_HOST and cname != EXPECTED_HOST.lower():
        errors.append(f"GitHub Pages cname must be {EXPECTED_HOST!r}, got {cname!r}")


def validate_dns(errors: list[str]) -> None:
    if not EXPECTED_HOST:
        errors.append(f"invalid expected canonical origin: {EXPECTED_ORIGIN!r}")
        return
    try:
        addresses = socket.getaddrinfo(EXPECTED_HOST, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        errors.append(f"canonical host {EXPECTED_HOST!r} does not resolve: {exc}")
        return
    if not addresses:
        errors.append(f"canonical host {EXPECTED_HOST!r} resolved without usable addresses")


def validate_homepage(errors: list[str]) -> None:
    try:
        status, final_url, content_type, body = request(EXPECTED_ORIGIN, accept="text/html")
    except Exception as exc:
        errors.append(f"canonical homepage request failed: {exc}")
        return

    if status != 200:
        errors.append(f"canonical homepage returned HTTP {status}")
        return
    final_host = (urlparse(final_url).hostname or "").lower()
    if final_host != EXPECTED_HOST.lower():
        errors.append(f"canonical homepage redirected to unexpected host {final_host!r}")
    if "html" not in content_type.lower():
        errors.append(f"canonical homepage content-type is not HTML: {content_type!r}")

    parser = HeadLinks()
    parser.feed(body)
    if EXPECTED_ORIGIN not in parser.canonical:
        errors.append(
            f"homepage canonical must contain {EXPECTED_ORIGIN!r}, got {parser.canonical!r}"
        )
    if (EXPECTED_LLMS, "text/markdown") not in parser.describedby:
        errors.append(
            "homepage must advertise the canonical llms.txt via "
            f"rel=describedby type=text/markdown; got {parser.describedby!r}"
        )


def validate_llms(errors: list[str]) -> None:
    try:
        status, final_url, _, body = request(EXPECTED_LLMS, accept="text/plain,text/markdown,*/*")
    except Exception as exc:
        errors.append(f"canonical llms.txt request failed: {exc}")
        return

    if status != 200:
        errors.append(f"canonical llms.txt returned HTTP {status}")
        return
    final_host = (urlparse(final_url).hostname or "").lower()
    if final_host != EXPECTED_HOST.lower():
        errors.append(f"canonical llms.txt redirected to unexpected host {final_host!r}")
    required = ("# AI Search Arab", EXPECTED_ORIGIN, "/methodology/", "/corrections/")
    for marker in required:
        if marker not in body:
            errors.append(f"canonical llms.txt missing required marker: {marker}")


def run_runtime_contract() -> list[str]:
    errors: list[str] = []
    validate_pages_configuration(errors)
    if errors:
        return errors

    if SETTLE_SECONDS > 0:
        print(f"Waiting {SETTLE_SECONDS}s for Pages/DNS to settle before live verification...")
        time.sleep(SETTLE_SECONDS)

    validate_dns(errors)
    if errors:
        return errors
    validate_homepage(errors)
    validate_llms(errors)
    return errors


def main() -> int:
    errors = run_runtime_contract()
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print(
        "✓ GitHub Pages runtime contract passed: workflow source, custom domain, "
        "canonical homepage, and llms.txt discovery are live"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
