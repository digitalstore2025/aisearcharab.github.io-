from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.models import LoginThrottle, User


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
