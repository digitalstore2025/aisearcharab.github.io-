from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit


class UnsafeTargetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    url: str
    host: str
    port: int
    addresses: tuple[str, ...]


def validate_public_ip(value: str) -> str:
    ip = ipaddress.ip_address(value)
    if not ip.is_global:
        raise UnsafeTargetError("target resolves to a non-public address")
    return ip.compressed


def validate_http_url(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeTargetError("only http and https targets are allowed")
    if not parsed.hostname:
        raise UnsafeTargetError("target hostname is required")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeTargetError("URL credentials are forbidden")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise UnsafeTargetError("localhost targets are forbidden")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeTargetError("invalid target port") from exc
    if port not in {80, 443}:
        raise UnsafeTargetError("only ports 80 and 443 are allowed")
    return parsed.scheme, host, port


def resolve_public_target(url: str) -> ResolvedTarget:
    _, host, port = validate_http_url(url)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return ResolvedTarget(url=url, host=host, port=port, addresses=(validate_public_ip(host),))

    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeTargetError("target hostname could not be resolved") from exc

    addresses = sorted({record[4][0] for record in records})
    if not addresses:
        raise UnsafeTargetError("target hostname has no addresses")
    validated = tuple(validate_public_ip(address) for address in addresses)
    return ResolvedTarget(url=url, host=host, port=port, addresses=validated)


def validate_redirect(previous: ResolvedTarget, location: str) -> ResolvedTarget:
    """Resolve every redirect hop again and allow only globally routable addresses."""
    target_url = urljoin(previous.url, location)
    return resolve_public_target(target_url)
