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
        generated_answers_provider="openai",
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
        "https://gateway.example:/v1",
        "https://gateway.example/v1/",
        "https://gateway.example/v1///",
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


def test_secure_runtime_requires_an_exact_gateway_origin_allowlist(settings: Settings) -> None:
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
        openai_base_url="https://gateway.internal.example:8443/v1",
    )
    with pytest.raises(ConfigurationError, match="OPENAI_GATEWAY_ALLOWED_ORIGINS"):
        staging.validate()
    with pytest.raises(ConfigurationError, match="OPENAI_GATEWAY_ALLOWED_ORIGINS"):
        replace(staging, openai_gateway_allowed_origins=("https://gateway.internal.example:443",)).validate()

    replace(staging, openai_gateway_allowed_origins=("https://gateway.internal.example:8443",)).validate()


def test_gateway_origin_allowlist_rejects_wildcards_and_paths(settings: Settings) -> None:
    for origin in ("https://*.example.com", "https://gateway.example/v1", "https://gateway.example:invalid", "https://gateway.example:", "https://gateway.example:0", "https://gateway.example:65536"):
        with pytest.raises(ConfigurationError, match="OPENAI_GATEWAY_ALLOWED_ORIGINS"):
            replace(settings, openai_gateway_allowed_origins=(origin,)).validate()


def test_development_http_gateway_is_limited_to_loopback(settings: Settings) -> None:
    replace(settings, openai_base_url="http://localhost:3001/v1").validate()
    replace(settings, openai_base_url="http://[::1]:3001/v1").validate()
    with pytest.raises(ConfigurationError, match="loopback"):
        replace(settings, openai_base_url="http://gateway.internal.example:3001/v1").validate()
    with pytest.raises(ConfigurationError, match="OPENAI_GATEWAY_ALLOWED_ORIGINS"):
        replace(settings, openai_base_url="https://gateway.internal.example:8443/v1").validate()
    replace(
        settings,
        openai_base_url="https://gateway.internal.example:8443/v1",
        openai_gateway_allowed_origins=("https://gateway.internal.example:8443",),
    ).validate()


def test_gateway_settings_are_appended_after_existing_positional_fields() -> None:
    from dataclasses import fields

    names = [field.name for field in fields(Settings)]
    assert names.index("openai_base_url") > names.index("generated_answer_window_seconds")
    assert names.index("openai_gateway_allowed_origins") > names.index("generated_answer_window_seconds")
    assert names.index("openai_gateway_api_key") > names.index("generated_answer_window_seconds")
    assert names.index("generated_answers_provider") > names.index("generated_answer_window_seconds")


def test_gateway_credentials_cannot_fall_back_to_the_public_openai_endpoint(settings: Settings) -> None:
    gateway_url = "https://gateway.internal.example:8443/v1"
    gateway_origin = ("https://gateway.internal.example:8443",)

    with pytest.raises(ConfigurationError, match="OPENAI_GATEWAY_API_KEY"):
        replace(
            settings,
            generated_answers_enabled=True,
            generated_answers_provider="gateway",
            openai_base_url=gateway_url,
            openai_gateway_allowed_origins=gateway_origin,
        ).validate()

    with pytest.raises(ConfigurationError, match="OPENAI_BASE_URL"):
        replace(settings, openai_gateway_api_key="gateway-token-not-a-production-secret").validate()

    gateway_settings = replace(
        settings,
        generated_answers_enabled=True,
        generated_answers_provider="gateway",
        openai_base_url=gateway_url,
        openai_gateway_allowed_origins=gateway_origin,
        openai_gateway_api_key="gateway-token-not-a-production-secret",
    )
    gateway_settings.validate()
    assert gateway_settings.generated_answers_provider == "gateway"
    assert gateway_settings.openai_gateway_api_key == "gateway-token-not-a-production-secret"

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        replace(gateway_settings, openai_api_key="public-openai-key-not-a-gateway-token").validate()


def test_default_openai_credentials_are_selected_only_with_explicit_openai_provider(settings: Settings) -> None:
    disabled_settings = replace(settings, openai_api_key="must-not-be-used-implicitly")
    assert disabled_settings.generated_answers_provider == "disabled"
    default_settings = replace(
        settings,
        generated_answers_provider="openai",
        openai_api_key="openai-key-not-a-gateway-token",
    )
    assert default_settings.generated_answers_provider == "openai"
    assert default_settings.openai_api_key == "openai-key-not-a-gateway-token"
    with pytest.raises(ConfigurationError, match="OPENAI_BASE_URL"):
        replace(
            default_settings,
            openai_base_url="https://gateway.internal.example/v1",
            openai_gateway_allowed_origins=("https://gateway.internal.example",),
        ).validate()


def test_settings_repr_redacts_database_and_provider_secrets(settings: Settings) -> None:
    configured = replace(
        settings,
        database_url="postgresql+psycopg://db-user:db-password@db.example/aisearcharab",
        query_hash_key="query-hash-secret-not-for-logs",
        login_throttle_key="login-throttle-secret-not-for-logs",
        mfa_encryption_key="mfa-encryption-secret-not-for-logs",
        openai_api_key="openai-secret-not-for-logs",
        openai_gateway_api_key="gateway-secret-not-for-logs",
    )
    rendered = repr(configured)
    for secret in (
        "db-password",
        "query-hash-secret-not-for-logs",
        "login-throttle-secret-not-for-logs",
        "mfa-encryption-secret-not-for-logs",
        "openai-secret-not-for-logs",
        "gateway-secret-not-for-logs",
    ):
        assert secret not in rendered


def test_provider_response_size_limit_is_bounded(settings: Settings) -> None:
    for value in (0, 16_383, 16_777_217):
        with pytest.raises(ConfigurationError, match="OPENAI_MAX_RESPONSE_BYTES"):
            replace(settings, openai_max_response_bytes=value).validate()

    replace(settings, openai_max_response_bytes=16_384).validate()
    replace(settings, openai_max_response_bytes=16_777_216).validate()
