from __future__ import annotations

from html.parser import HTMLParser
import socket
import ssl
import urllib.parse
import urllib.request

from .engine import Gate, Status


class _CanonicalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonical: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return
        data = dict(attrs)
        rel = (data.get("rel") or "").lower().split()
        if "canonical" in rel and data.get("href"):
            self.canonical = data["href"]


def _get(url: str, timeout: float = 10.0) -> tuple[int, dict[str, str], bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "AISearch-Readiness-Guardian/1.0"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return (getattr(response, "status", 200), {key.lower(): value for key, value in response.headers.items()}, response.read(1024 * 1024), response.geturl())


def _tls_check(hostname: str, timeout: float = 8.0) -> tuple[bool, str]:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as tls:
                cert = tls.getpeercert()
                return True, f"TLS certificate validated; expires={cert.get('notAfter', 'unknown')}"
    except Exception as exc:
        return False, f"TLS validation failed: {exc}"


def run_live_checks(base_url: str) -> list[Gate]:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Live checks require an https:// URL.")

    results: list[Gate] = []
    hostname = parsed.hostname
    tls_ok, evidence = _tls_check(hostname)
    results.append(Gate(id="LIVE-TLS", category="Search/Trust", gate="TLS certificate validation", status=Status.PASS if tls_ok else Status.FAIL, blocking=True, verified=tls_ok, trust_surface=True, evidence=evidence, source=base_url, acceptance="Valid TLS certificate chain for the production hostname.", next_action="" if tls_ok else "Repair DNS/certificate provisioning before release."))

    try:
        status, headers, body, final_url = _get(base_url)
        http_ok = 200 <= status < 400
        results.append(Gate(id="LIVE-HTTPS", category="Search/Trust", gate="HTTPS endpoint reachability", status=Status.PASS if http_ok else Status.FAIL, blocking=True, verified=http_ok, trust_surface=True, evidence=f"HTTP {status}; final_url={final_url}", source=base_url, acceptance="Production HTTPS endpoint is reachable and returns success/redirect.", next_action="" if http_ok else "Repair deployment, routing, or DNS."))

        missing: list[str] = []
        if "strict-transport-security" not in headers:
            missing.append("Strict-Transport-Security")
        if headers.get("x-content-type-options", "").strip().lower() != "nosniff":
            missing.append("X-Content-Type-Options: nosniff")
        if "referrer-policy" not in headers:
            missing.append("Referrer-Policy")
        csp = headers.get("content-security-policy", "").lower()
        if "x-frame-options" not in headers and "frame-ancestors" not in csp:
            missing.append("clickjacking control")

        headers_ok = not missing
        results.append(Gate(id="LIVE-HEADERS", category="Security", gate="Baseline security headers", status=Status.PASS if headers_ok else Status.FAIL, blocking=True, verified=headers_ok, evidence="All required baseline headers present." if headers_ok else f"Missing: {', '.join(missing)}", source=base_url, acceptance="HSTS, nosniff, Referrer-Policy, and clickjacking control are present.", next_action="" if headers_ok else "Add missing security headers and retest."))

        parser = _CanonicalParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        expected = base_url.rstrip("/")
        canonical_ok = bool(parser.canonical) and parser.canonical.rstrip("/") == expected
        results.append(Gate(id="LIVE-CANONICAL", category="Search/Trust", gate="Canonical URL", status=Status.PASS if canonical_ok else Status.FAIL, blocking=False, verified=canonical_ok, trust_surface=True, evidence=f"canonical={parser.canonical!r}; expected={expected!r}", source=base_url, acceptance="Homepage canonical equals the production URL.", next_action="" if canonical_ok else "Add or correct the homepage canonical tag."))
    except Exception as exc:
        results.append(Gate(id="LIVE-HTTPS", category="Search/Trust", gate="HTTPS endpoint reachability", status=Status.FAIL, blocking=True, verified=False, trust_surface=True, evidence=f"HTTPS check failed: {exc}", source=base_url, acceptance="Production HTTPS endpoint is reachable.", next_action="Repair deployment, DNS, or network path."))

    trust_paths = {"/about": False, "/contact": True, "/privacy": True, "/terms": True, "/security": False, "/robots.txt": True, "/sitemap.xml": True}
    for path, blocking in trust_paths.items():
        url = base_url.rstrip("/") + path
        try:
            status, _, body, final_url = _get(url)
            ok = 200 <= status < 300 and bool(body.strip())
            evidence = f"HTTP {status}; bytes={len(body)}; final_url={final_url}"
        except Exception as exc:
            ok = False
            evidence = f"Check failed: {exc}"
        results.append(Gate(id="TRUST-" + path.strip("/").replace(".", "-").upper(), category="Search/Trust", gate=f"Trust surface {path}", status=Status.PASS if ok else Status.FAIL, blocking=blocking, verified=ok, trust_surface=True, evidence=evidence, source=url, acceptance=f"{path} exists and returns substantive content.", next_action="" if ok else f"Publish or repair {path}."))
    return results
