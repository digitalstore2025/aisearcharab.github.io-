from __future__ import annotations

import ipaddress
import math
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from .geo.network_security import ResolvedTarget, UnsafeTargetError, resolve_public_target, validate_http_url, validate_public_ip

_SOURCE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_PORTS = frozenset({80, 443})


class ResearchPolicyError(ValueError):
    """Base exception for external-research policy violations."""


class UnknownResearchSource(ResearchPolicyError):
    """Raised when an unregistered source identifier is requested."""


class ResearchTargetDenied(ResearchPolicyError):
    """Raised when a URL, redirect, or connected peer violates source policy."""


def _normalize_hostname(value: str) -> str:
    raw = value.strip().rstrip(".")
    if not raw or "*" in raw:
        raise ResearchPolicyError("source host must be an explicit DNS name")
    try:
        host = raw.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ResearchPolicyError("source host is not a valid IDNA hostname") from exc
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ResearchPolicyError("literal IP addresses cannot be research source allowlist entries")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise ResearchPolicyError("localhost cannot be a research source allowlist entry")
    if len(host) > 253 or any(not label or len(label) > 63 for label in host.split(".")):
        raise ResearchPolicyError("source host is not a valid DNS name")
    return host


@dataclass(frozen=True, slots=True)
class ResearchSourcePolicy:
    source_id: str
    allowed_hosts: frozenset[str]
    allow_subdomains: bool = False
    allowed_schemes: frozenset[str] = frozenset({"https"})
    allowed_ports: frozenset[int] = frozenset({443})
    max_redirects: int = 3
    max_response_bytes: int = 2 * 1024 * 1024
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        source_id = self.source_id.strip()
        if not _SOURCE_ID.fullmatch(source_id):
            raise ResearchPolicyError("source_id contains unsupported characters or length")
        if not self.allowed_hosts:
            raise ResearchPolicyError("research source must allow at least one host")
        normalized_hosts = frozenset(_normalize_hostname(host) for host in self.allowed_hosts)
        schemes = frozenset(str(value).lower() for value in self.allowed_schemes)
        if not schemes or not schemes.issubset(_ALLOWED_SCHEMES):
            raise ResearchPolicyError("allowed_schemes must be a non-empty subset of http/https")
        ports = frozenset(self.allowed_ports)
        if not ports or not ports.issubset(_ALLOWED_PORTS):
            raise ResearchPolicyError("allowed_ports must be a non-empty subset of 80/443")
        if any((scheme == "https" and 443 not in ports) or (scheme == "http" and 80 not in ports) for scheme in schemes):
            raise ResearchPolicyError("allowed ports must include the conventional port for every allowed scheme")
        if isinstance(self.max_redirects, bool) or not 0 <= self.max_redirects <= 10:
            raise ResearchPolicyError("max_redirects must be between 0 and 10")
        if isinstance(self.max_response_bytes, bool) or not 1 <= self.max_response_bytes <= 10 * 1024 * 1024:
            raise ResearchPolicyError("max_response_bytes must be between 1 byte and 10 MiB")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)):
            raise ResearchPolicyError("timeout_seconds must be numeric")
        timeout = float(self.timeout_seconds)
        if not math.isfinite(timeout) or not 1.0 <= timeout <= 120.0:
            raise ResearchPolicyError("timeout_seconds must be finite and between 1 and 120")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "allowed_hosts", normalized_hosts)
        object.__setattr__(self, "allowed_schemes", schemes)
        object.__setattr__(self, "allowed_ports", ports)
        object.__setattr__(self, "timeout_seconds", timeout)

    def allows_host(self, host: str) -> bool:
        normalized = _normalize_hostname(host)
        if normalized in self.allowed_hosts:
            return True
        if not self.allow_subdomains:
            return False
        return any(normalized.endswith(f".{allowed}") for allowed in self.allowed_hosts)


@dataclass(frozen=True, slots=True)
class ResearchTargetPreflight:
    source_id: str
    resolved: ResolvedTarget
    redirect_count: int
    max_response_bytes: int
    timeout_seconds: float


class ResearchSourceRegistry:
    def __init__(self, sources: tuple[ResearchSourcePolicy, ...] | list[ResearchSourcePolicy]) -> None:
        indexed: dict[str, ResearchSourcePolicy] = {}
        for source in sources:
            if source.source_id in indexed:
                raise ResearchPolicyError(f"duplicate research source_id: {source.source_id}")
            indexed[source.source_id] = source
        self._sources = indexed

    def get(self, source_id: str) -> ResearchSourcePolicy:
        source = self._sources.get(source_id)
        if source is None:
            raise UnknownResearchSource(f"unregistered research source: {source_id}")
        return source

    def preflight(self, source_id: str, url: str) -> ResearchTargetPreflight:
        source = self.get(source_id)
        _validate_source_url(source, url)
        try:
            resolved = resolve_public_target(url)
        except UnsafeTargetError as exc:
            raise ResearchTargetDenied(str(exc)) from exc
        return ResearchTargetPreflight(
            source_id=source.source_id,
            resolved=resolved,
            redirect_count=0,
            max_response_bytes=source.max_response_bytes,
            timeout_seconds=source.timeout_seconds,
        )

    def redirect(self, previous: ResearchTargetPreflight, location: str) -> ResearchTargetPreflight:
        source = self.get(previous.source_id)
        if previous.redirect_count >= source.max_redirects:
            raise ResearchTargetDenied("research source redirect limit exceeded")
        target_url = urljoin(previous.resolved.url, location)
        _validate_source_url(source, target_url)
        try:
            resolved = resolve_public_target(target_url)
        except UnsafeTargetError as exc:
            raise ResearchTargetDenied(str(exc)) from exc
        return ResearchTargetPreflight(
            source_id=source.source_id,
            resolved=resolved,
            redirect_count=previous.redirect_count + 1,
            max_response_bytes=source.max_response_bytes,
            timeout_seconds=source.timeout_seconds,
        )


def _validate_source_url(source: ResearchSourcePolicy, url: str) -> None:
    try:
        scheme, host, port = validate_http_url(url)
    except UnsafeTargetError as exc:
        raise ResearchTargetDenied(str(exc)) from exc
    if scheme not in source.allowed_schemes:
        raise ResearchTargetDenied("target scheme is not allowlisted for this research source")
    if port not in source.allowed_ports:
        raise ResearchTargetDenied("target port is not allowlisted for this research source")
    try:
        allowed_host = source.allows_host(host)
    except ResearchPolicyError as exc:
        raise ResearchTargetDenied("target host is not an allowed DNS name") from exc
    if not allowed_host:
        raise ResearchTargetDenied("target host is not allowlisted for this research source")


def validate_connected_peer(preflight: ResearchTargetPreflight, peer_ip: str) -> str:
    """Verify that the actual connected peer matches a public preflight address.

    A preflight is not permission to use a normal hostname-re-resolving HTTP client.
    Future fetchers must pin/connect to a preflight address, preserve the original
    hostname for HTTP/TLS verification, and call this check on the connected peer.
    """
    try:
        normalized = validate_public_ip(peer_ip)
    except (UnsafeTargetError, ValueError) as exc:
        raise ResearchTargetDenied("connected peer is not a public IP") from exc
    if normalized not in preflight.resolved.addresses:
        raise ResearchTargetDenied("connected peer does not match preflight DNS addresses")
    return normalized
