from __future__ import annotations

import base64
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.config import ConfigurationError, Settings
from aisearcharab_api.database import get_db
from aisearcharab_api.main import create_app
from aisearcharab_api.mfa import current_counter, decrypt_totp_secret, totp_code
from aisearcharab_api.models import User
from conftest import OWNER_EMAIL, OWNER_PASSWORD, csrf_from_client

TEST_MFA_KEY = "ci-test-mfa-encryption-key-not-a-secret-2026"


@pytest.fixture()
def mfa_client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:3000",),
        allowed_hosts=("testserver",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        session_ttl_minutes=60,
        session_idle_minutes=30,
        require_mfa_for_privileged=True,
        mfa_encryption_key=TEST_MFA_KEY,
    )
    settings.validate()
    app = create_app(settings)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def test_totp_matches_rfc6238_sha1_vector() -> None:
    secret = base64.b32encode(b"12345678901234567890").decode("ascii").rstrip("=")
    vectors = [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ]
    for timestamp, expected in vectors:
        assert totp_code(secret, counter=timestamp // 30, digits=8) == expected


def test_privileged_mfa_requires_key() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:3000",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        require_mfa_for_privileged=True,
    )
    with pytest.raises(ConfigurationError, match="MFA_ENCRYPTION_KEY"):
        settings.validate()


def test_staging_requires_privileged_mfa() -> None:
    settings = Settings(
        environment="staging",
        database_url="postgresql+psycopg://app:secret@db/app",
        allowed_origins=("https://staging.aisearcharab.com",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        require_mfa_for_privileged=False,
        mfa_encryption_key=TEST_MFA_KEY,
    )
    with pytest.raises(ConfigurationError, match="REQUIRE_MFA_FOR_PRIVILEGED"):
        settings.validate()


def test_owner_must_enroll_and_verify_mfa_before_admin_access(
    mfa_client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    login = mfa_client.post("/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    assert login.status_code == 200
    csrf = csrf_from_client(mfa_client)
    headers = {"X-CSRF-Token": csrf}

    blocked = mfa_client.get("/v1/auth/me")
    assert blocked.status_code == 401
    assert blocked.json()["detail"] == "multi-factor authentication required"

    status_before = mfa_client.get("/v1/auth/mfa/status", headers=headers)
    assert status_before.status_code == 200
    assert status_before.json()["required"] is True
    assert status_before.json()["enrolled"] is False
    assert status_before.json()["verified"] is False

    started = mfa_client.post(
        "/v1/auth/mfa/enroll/start",
        headers=headers,
        json={"password": OWNER_PASSWORD},
    )
    assert started.status_code == 200
    secret = started.json()["secret"]
    assert started.json()["otpauth_uri"].startswith("otpauth://totp/")

    with session_factory() as db:
        owner = db.query(User).filter(User.email == OWNER_EMAIL).one()
        assert owner.mfa_pending_secret_encrypted
        assert secret not in owner.mfa_pending_secret_encrypted
        assert decrypt_totp_secret(owner.mfa_pending_secret_encrypted, TEST_MFA_KEY) == secret

    code = totp_code(secret, counter=current_counter())
    confirmed = mfa_client.post("/v1/auth/mfa/enroll/confirm", headers=headers, json={"code": code})
    assert confirmed.status_code == 200
    recovery_codes = confirmed.json()["recovery_codes"]
    assert len(recovery_codes) == 10
    assert len(set(recovery_codes)) == 10
    assert all(code not in confirmed.text.replace(code, "", 1) for code in [])

    assert mfa_client.get("/v1/auth/me").status_code == 200
    status_after = mfa_client.get("/v1/auth/mfa/status", headers=headers)
    assert status_after.status_code == 200
    assert status_after.json()["enrolled"] is True
    assert status_after.json()["verified"] is True
    assert status_after.json()["recovery_codes_remaining"] == 10

    assert mfa_client.post("/v1/auth/logout", headers=headers).status_code == 204

    second_login = mfa_client.post("/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    assert second_login.status_code == 200
    second_headers = {"X-CSRF-Token": csrf_from_client(mfa_client)}
    replay = mfa_client.post("/v1/auth/mfa/verify", headers=second_headers, json={"code": code})
    assert replay.status_code == 401
    assert replay.json()["detail"] == "invalid authentication code"

    recovered = mfa_client.post(
        "/v1/auth/mfa/verify",
        headers=second_headers,
        json={"code": recovery_codes[0]},
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovery_code_used"] is True
    assert mfa_client.get("/v1/auth/me").status_code == 200

    assert mfa_client.post("/v1/auth/logout", headers=second_headers).status_code == 204
    assert mfa_client.post("/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}).status_code == 200
    third_headers = {"X-CSRF-Token": csrf_from_client(mfa_client)}
    reused_recovery = mfa_client.post(
        "/v1/auth/mfa/verify",
        headers=third_headers,
        json={"code": recovery_codes[0]},
    )
    assert reused_recovery.status_code == 401


def test_privileged_mfa_cannot_be_disabled_when_policy_requires_it(
    mfa_client: TestClient,
) -> None:
    assert mfa_client.post("/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}).status_code == 200
    headers = {"X-CSRF-Token": csrf_from_client(mfa_client)}
    started = mfa_client.post("/v1/auth/mfa/enroll/start", headers=headers, json={"password": OWNER_PASSWORD})
    secret = started.json()["secret"]
    code = totp_code(secret, counter=current_counter())
    assert mfa_client.post("/v1/auth/mfa/enroll/confirm", headers=headers, json={"code": code}).status_code == 200
    assert mfa_client.post("/v1/auth/step-up", headers=headers, json={"password": OWNER_PASSWORD}).status_code == 200
    disabled = mfa_client.post("/v1/auth/mfa/disable", headers=headers)
    assert disabled.status_code == 409
    assert disabled.json()["detail"] == "MFA is mandatory for this role"
