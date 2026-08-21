from __future__ import annotations

import hashlib
import hmac
import ipaddress
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import LoginThrottle

_DEV_KEY = "aisearcharab-development-login-throttle-key-2026"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@lru_cache(maxsize=32)
def _parse_trusted_proxy_networks(
    cidrs: tuple[str, ...],
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    # Settings.validate() rejects malformed and trust-everywhere networks. The
    # tuple is immutable configuration, so parsed networks can be safely reused
    # on the pre-authentication hot path.
    return tuple(ipaddress.ip_network(cidr, strict=False) for cidr in cidrs)


def _trusted_proxy_networks(request: Request) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return _parse_trusted_proxy_networks(request.app.state.settings.trusted_proxy_cidrs)


def _in_trusted_proxy_networks(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    return any(address.version == network.version and address in network for network in networks)


def _forwarded_chain(request: Request) -> list[str]:
    """Flatten every X-Forwarded-For field in wire order.

    A trusted proxy may append a second header field instead of rewriting an
    attacker-supplied field. Reading all values ensures the authoritative hop
    appended by the trusted proxy remains the right-most forwarded address.
    """
    chain: list[str] = []
    for field in request.headers.getlist("x-forwarded-for"):
        chain.extend(item.strip() for item in field.split(",") if item.strip())
    return chain


def _source(request: Request) -> str:
    """Return a stable pre-auth source identity without trusting arbitrary headers.

    The direct ASGI peer remains authoritative unless it belongs to an explicitly
    configured trusted proxy CIDR. Only then do we walk all X-Forwarded-For
    fields from the right, discard known proxy hops, and use the nearest
    untrusted address.

    This prevents a reverse proxy from collapsing all clients into one throttle
    identity while still preventing direct clients from spoofing X-Forwarded-For.
    """
    client = request.client
    peer = client.host if client and client.host else "unknown-peer"
    networks = _trusted_proxy_networks(request)
    if not networks:
        return peer

    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not _in_trusted_proxy_networks(peer_ip, networks):
        return peer_ip.compressed

    chain = _forwarded_chain(request)
    if not chain:
        return peer_ip.compressed

    # A conforming trusted proxy appends its observed client address. Walking
    # from the right means attacker-supplied entries to the left cannot override
    # the nearest untrusted hop that the trusted proxy observed.
    chain.append(peer_ip.compressed)
    for raw in reversed(chain):
        try:
            candidate = ipaddress.ip_address(raw)
        except ValueError:
            # Malformed data from the trusted chain is not used as identity.
            return peer_ip.compressed
        if _in_trusted_proxy_networks(candidate, networks):
            continue
        return candidate.compressed

    return peer_ip.compressed


def throttle_key(request: Request, normalized_email: str) -> str:
    settings = request.app.state.settings
    secret = settings.login_throttle_key or _DEV_KEY
    payload = f"login\x00{_source(request)}\x00{normalized_email}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _retry_after(blocked_until: datetime, now: datetime) -> int:
    return max(1, int((_aware(blocked_until) - now).total_seconds()) + 1)


def enforce_login_throttle(db: Session, request: Request, normalized_email: str) -> str:
    """Reject a currently blocked source/account pair and return its opaque key."""
    key_hash = throttle_key(request, normalized_email)
    row = db.scalar(select(LoginThrottle).where(LoginThrottle.key_hash == key_hash).with_for_update())
    if row is None:
        return key_hash

    now = datetime.now(timezone.utc)
    settings = request.app.state.settings
    if row.blocked_until is not None and _aware(row.blocked_until) > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many authentication attempts",
            headers={"Retry-After": str(_retry_after(row.blocked_until, now))},
        )

    window_end = _aware(row.window_started_at) + timedelta(seconds=settings.login_throttle_window_seconds)
    if window_end <= now:
        row.failure_count = 0
        row.window_started_at = now
        row.blocked_until = None
    return key_hash


def _get_or_create_locked(db: Session, key_hash: str, now: datetime) -> LoginThrottle:
    row = db.scalar(select(LoginThrottle).where(LoginThrottle.key_hash == key_hash).with_for_update())
    if row is not None:
        return row

    try:
        with db.begin_nested():
            row = LoginThrottle(key_hash=key_hash, failure_count=0, window_started_at=now, updated_at=now)
            db.add(row)
            db.flush()
        return row
    except IntegrityError:
        # Another replica may have created the same throttle row concurrently.
        row = db.scalar(select(LoginThrottle).where(LoginThrottle.key_hash == key_hash).with_for_update())
        if row is None:
            raise
        return row


def record_login_failure(db: Session, request: Request, key_hash: str) -> bool:
    """Record one failed pre-auth attempt. Returns True when a block is activated."""
    now = datetime.now(timezone.utc)
    settings = request.app.state.settings
    row = _get_or_create_locked(db, key_hash, now)
    window_end = _aware(row.window_started_at) + timedelta(seconds=settings.login_throttle_window_seconds)
    if window_end <= now:
        row.failure_count = 0
        row.window_started_at = now
        row.blocked_until = None

    row.failure_count += 1
    row.updated_at = now
    if row.failure_count >= settings.login_throttle_max_failures:
        row.blocked_until = now + timedelta(seconds=settings.login_throttle_block_seconds)
        return True
    return False


def clear_login_throttle(db: Session, key_hash: str) -> None:
    db.execute(delete(LoginThrottle).where(LoginThrottle.key_hash == key_hash))
