from dataclasses import replace

import pytest

from aisearcharab_api.config import ConfigurationError, Settings


def test_generated_answers_are_blocked_in_production_until_operational_controls_exist(settings: Settings) -> None:
    production = replace(
        settings,
        environment="production",
        database_url="postgresql+psycopg://user:password@db.example/aisearcharab",
        allowed_origins=("https://aisearcharab.com",),
        allowed_hosts=("aisearcharab.com",),
        enforce_separation_of_duties=True,
        require_mfa_for_privileged=True,
        mfa_encryption_key="test-mfa-encryption-key-32-bytes-long",
        login_throttle_key="test-login-throttle-key-32-bytes-long",
        generated_answers_enabled=True,
        openai_api_key="test-openai-key-not-a-production-secret",
    )
    with pytest.raises(ConfigurationError, match="distributed rate limiting and observability"):
        production.validate()


def test_openai_base_url_accepts_an_explicit_v1_gateway_in_development(settings: Settings) -> None:
    replace(settings, openai_base_url="http://127.0.0.1:3001/v1").validate()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://gateway.example/v2",
        "https://user:password@gateway.example/v1",
        "https://gateway.example/v1?token=secret",
        "https://gateway.example/v1#fragment",
        "https://gateway.example:invalid/v1",
        "https://gateway.example:65536/v1",
        "http://gateway.internal.example/v1",
    ],
)
def test_openai_base_url_rejects_ambiguous_or_credential_bearing_urls(
    settings: Settings,
    base_url: str,
) -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_BASE_URL"):
        replace(settings, openai_base_url=base_url).validate()


def test_secure_runtime_requires_https_for_openai_gateway(settings: Settings) -> None:
    staging = replace(
        settings,
        environment="staging",
        database_url="postgresql+psycopg://user:password@db.example/aisearcharab",
        allowed_origins=("https://aisearcharab.com",),
        allowed_hosts=("aisearcharab.com",),
        require_mfa_for_privileged=True,
        mfa_encryption_key="test-mfa-encryption-key-32-bytes-long",
        login_throttle_key="test-login-throttle-key-32-bytes-long",
        openai_base_url="http://gateway.internal:3001/v1",
    )
    with pytest.raises(ConfigurationError, match="staging and production require HTTPS"):
        staging.validate()


def test_secure_runtime_requires_an_exact_gateway_host_allowlist(settings: Settings) -> None:
    staging = replace(
        settings,
        environment="staging",
        database_url="postgresql+psycopg://user:password@db.example/aisearcharab",
        allowed_origins=("https://aisearcharab.com",),
        allowed_hosts=("aisearcharab.com",),
        enforce_separation_of_duties=True,
        require_mfa_for_privileged=True,
        mfa_encryption_key="test-mfa-encryption-key-32-bytes-long",
        login_throttle_key="test-login-throttle-key-32-bytes-long",
        openai_base_url="https://gateway.internal.example/v1",
    )
    with pytest.raises(ConfigurationError, match="OPENAI_ALLOWED_HOSTS"):
        staging.validate()

    replace(staging, openai_allowed_hosts=("gateway.internal.example",)).validate()


def test_gateway_host_allowlist_rejects_wildcards(settings: Settings) -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_ALLOWED_HOSTS"):
        replace(settings, openai_allowed_hosts=("*.example.com",)).validate()


def test_development_http_gateway_is_limited_to_loopback(settings: Settings) -> None:
    replace(settings, openai_base_url="http://localhost:3001/v1").validate()
    replace(settings, openai_base_url="http://[::1]:3001/v1").validate()
    with pytest.raises(ConfigurationError, match="loopback"):
        replace(settings, openai_base_url="http://gateway.internal.example:3001/v1").validate()
