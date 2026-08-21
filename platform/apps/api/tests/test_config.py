import pytest

from aisearcharab_api.config import ConfigurationError, Settings

MFA_KEY = "test-only-mfa-encryption-key-not-a-secret-2026"
THROTTLE_KEY = "test-only-login-throttle-key-not-a-secret-2026"


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "database_url": "postgresql+psycopg://app:secret@db/app",
        "allowed_origins": ("https://aisearcharab.com",),
        "allowed_hosts": ("aisearcharab.com",),
        "api_prefix": "/v1",
        "max_search_limit": 20,
        "log_queries": False,
        "enforce_separation_of_duties": True,
        "require_mfa_for_privileged": True,
        "mfa_encryption_key": MFA_KEY,
        "login_throttle_key": THROTTLE_KEY,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_sqlite() -> None:
    settings = production_settings(database_url="sqlite:///unsafe.db")
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_rejects_wildcard_cors() -> None:
    settings = production_settings(allowed_origins=("*",))
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_rejects_wildcard_hosts() -> None:
    settings = production_settings(allowed_hosts=("*",))
    with pytest.raises(ConfigurationError, match="Wildcard hosts"):
        settings.validate()


def test_query_logging_requires_keyed_hash_secret() -> None:
    settings = Settings(
        environment="staging",
        database_url="postgresql+psycopg://app:secret@db/app",
        allowed_origins=("https://staging.aisearcharab.com",),
        allowed_hosts=("staging.aisearcharab.com",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=True,
        query_hash_key="short",
        require_mfa_for_privileged=True,
        mfa_encryption_key=MFA_KEY,
        login_throttle_key=THROTTLE_KEY,
    )
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_rejects_insecure_or_path_cors_origin() -> None:
    settings = production_settings(allowed_origins=("http://aisearcharab.com/path",))
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_requires_separation_of_duties() -> None:
    settings = production_settings(enforce_separation_of_duties=False)
    with pytest.raises(ConfigurationError, match="SEPARATION_OF_DUTIES"):
        settings.validate()


def test_production_requires_privileged_mfa() -> None:
    settings = production_settings(require_mfa_for_privileged=False)
    with pytest.raises(ConfigurationError, match="REQUIRE_MFA_FOR_PRIVILEGED"):
        settings.validate()


def test_production_requires_mfa_encryption_key() -> None:
    settings = production_settings(mfa_encryption_key=None)
    with pytest.raises(ConfigurationError, match="MFA_ENCRYPTION_KEY"):
        settings.validate()


def test_production_requires_login_throttle_key() -> None:
    settings = production_settings(login_throttle_key=None)
    with pytest.raises(ConfigurationError, match="LOGIN_THROTTLE_KEY"):
        settings.validate()


def test_login_throttle_key_must_be_strong() -> None:
    settings = production_settings(login_throttle_key="too-short")
    with pytest.raises(ConfigurationError, match="LOGIN_THROTTLE_KEY"):
        settings.validate()


def test_trusted_proxy_cidr_must_be_valid_network() -> None:
    settings = production_settings(trusted_proxy_cidrs=("not-a-network",))
    with pytest.raises(ConfigurationError, match="TRUSTED_PROXY_CIDRS"):
        settings.validate()


@pytest.mark.parametrize("cidr", ["0.0.0.0/0", "::/0"])
def test_trusted_proxy_cidr_rejects_trust_everywhere(cidr: str) -> None:
    settings = production_settings(trusted_proxy_cidrs=(cidr,))
    with pytest.raises(ConfigurationError, match="TRUSTED_PROXY_CIDRS"):
        settings.validate()


def test_trusted_proxy_cidr_accepts_explicit_proxy_network() -> None:
    settings = production_settings(trusted_proxy_cidrs=("10.0.0.0/24", "2001:db8:1::/64"))
    settings.validate()


def test_idle_timeout_must_be_lower_than_absolute_timeout() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:8000",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        session_ttl_minutes=30,
        session_idle_minutes=30,
    )
    with pytest.raises(ConfigurationError, match="SESSION_IDLE_MINUTES"):
        settings.validate()
