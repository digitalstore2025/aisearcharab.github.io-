from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.login_throttle import _source, throttle_key
from aisearcharab_api.models import LoginThrottle, User


def _request(
    peer: str,
    *,
    forwarded_for: str = "",
    trusted_proxy_cidrs: tuple[str, ...] = (),
) -> SimpleNamespace:
    settings = SimpleNamespace(
        trusted_proxy_cidrs=trusted_proxy_cidrs,
        login_throttle_key="test-only-login-throttle-key-not-a-secret-2026",
    )
    return SimpleNamespace(
        client=SimpleNamespace(host=peer),
        headers={"x-forwarded-for": forwarded_for} if forwarded_for else {},
        app=SimpleNamespace(state=SimpleNamespace(settings=settings)),
    )


def test_untrusted_peer_cannot_spoof_forwarded_source() -> None:
    request = _request(
        "198.51.100.10",
        forwarded_for="203.0.113.77",
        trusted_proxy_cidrs=("10.0.0.0/24",),
    )
    assert _source(request) == "198.51.100.10"


def test_trusted_proxy_uses_nearest_untrusted_forwarded_client() -> None:
    request = _request(
        "10.0.0.5",
        forwarded_for="198.51.100.77, 203.0.113.20, 10.0.0.4",
        trusted_proxy_cidrs=("10.0.0.0/24",),
    )
    assert _source(request) == "203.0.113.20"


def test_trusted_proxy_keeps_distinct_clients_in_distinct_throttle_buckets() -> None:
    first = _request(
        "10.0.0.5",
        forwarded_for="203.0.113.20",
        trusted_proxy_cidrs=("10.0.0.0/24",),
    )
    second = _request(
        "10.0.0.5",
        forwarded_for="203.0.113.21",
        trusted_proxy_cidrs=("10.0.0.0/24",),
    )
    assert throttle_key(first, "owner@example.com") != throttle_key(second, "owner@example.com")


def test_malformed_forwarded_chain_fails_closed_to_peer() -> None:
    request = _request(
        "10.0.0.5",
        forwarded_for="not-an-ip",
        trusted_proxy_cidrs=("10.0.0.0/24",),
    )
    assert _source(request) == "10.0.0.5"


def test_pre_auth_failures_are_throttled_without_locking_account(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    for _ in range(8):
        response = client.post(
            "/v1/auth/login",
            json={"email": owner_credentials["email"], "password": "wrong-password-value"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid credentials"

    blocked = client.post(
        "/v1/auth/login",
        json={"email": owner_credentials["email"], "password": "wrong-password-value"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "too many authentication attempts"
    assert int(blocked.headers["retry-after"]) >= 1

    with session_factory() as db:
        user = db.query(User).filter(User.email == owner_credentials["email"]).one()
        assert user.failed_login_count == 0
        assert user.locked_until is None
        throttle = db.query(LoginThrottle).one()
        assert throttle.failure_count == 8
        assert throttle.blocked_until is not None
        assert len(throttle.key_hash) == 64
        assert owner_credentials["email"] not in throttle.key_hash


def test_invalid_email_uses_same_generic_failure_contract(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/login",
        json={"email": "not-an-email", "password": "wrong-password-value"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"
