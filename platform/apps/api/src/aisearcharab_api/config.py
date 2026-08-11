from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    """Raised when runtime configuration is unsafe or incomplete."""


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _valid_origin(value: str, *, require_https: bool) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in ({"https"} if require_https else {"http", "https"}):
        return False
    if not parsed.netloc or parsed.username or parsed.password:
        return False
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        return False
    return True


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    database_url: str
    allowed_origins: tuple[str, ...]
    api_prefix: str
    max_search_limit: int
    log_queries: bool
    query_hash_key: str | None = None
    session_ttl_minutes: int = 720
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    password_min_length: int = 14

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.environment in {"staging", "production"}

    @property
    def session_cookie_name(self) -> str:
        return "__Host-ais-admin" if self.secure_cookies else "ais_admin_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-ais-csrf" if self.secure_cookies else "ais_admin_csrf"

    def validate(self) -> None:
        if self.environment not in {"development", "test", "staging", "production"}:
            raise ConfigurationError("APP_ENV must be development, test, staging, or production")
        if not self.database_url:
            raise ConfigurationError("DATABASE_URL is required")
        if not self.api_prefix.startswith("/") or self.api_prefix == "/":
            raise ConfigurationError("API_PREFIX must start with '/' and include a version segment")
        if not 1 <= self.max_search_limit <= 100:
            raise ConfigurationError("MAX_SEARCH_LIMIT must be between 1 and 100")
        if not 15 <= self.session_ttl_minutes <= 1440:
            raise ConfigurationError("SESSION_TTL_MINUTES must be between 15 and 1440")
        if not 3 <= self.login_max_failures <= 20:
            raise ConfigurationError("LOGIN_MAX_FAILURES must be between 3 and 20")
        if not 1 <= self.login_lock_minutes <= 1440:
            raise ConfigurationError("LOGIN_LOCK_MINUTES must be between 1 and 1440")
        if not 12 <= self.password_min_length <= 128:
            raise ConfigurationError("PASSWORD_MIN_LENGTH must be between 12 and 128")
        if not self.allowed_origins:
            raise ConfigurationError("ALLOWED_ORIGINS must contain at least one explicit origin")
        if any(not _valid_origin(origin, require_https=self.is_production) for origin in self.allowed_origins):
            raise ConfigurationError("ALLOWED_ORIGINS must contain valid origins without paths, credentials, queries, or fragments")
        if self.log_queries and (self.query_hash_key is None or len(self.query_hash_key.encode("utf-8")) < 32):
            raise ConfigurationError("QUERY_HASH_KEY must contain at least 32 bytes when query logging is enabled")
        if self.is_production:
            if self.database_url.startswith("sqlite"):
                raise ConfigurationError("SQLite is not allowed in production")
            if "*" in self.allowed_origins:
                raise ConfigurationError("Wildcard CORS origins are not allowed in production")
            if "change-me" in self.database_url.lower():
                raise ConfigurationError("DATABASE_URL contains a placeholder credential")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings(
        environment=os.getenv("APP_ENV", "development").strip().lower(),
        database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///./aisearcharab.db").strip(),
        allowed_origins=_csv(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")),
        api_prefix=os.getenv("API_PREFIX", "/v1").rstrip("/"),
        max_search_limit=_int("MAX_SEARCH_LIMIT", os.getenv("MAX_SEARCH_LIMIT", "20")),
        log_queries=_bool(os.getenv("LOG_SEARCH_QUERIES", "false")),
        query_hash_key=os.getenv("QUERY_HASH_KEY") or None,
        session_ttl_minutes=_int("SESSION_TTL_MINUTES", os.getenv("SESSION_TTL_MINUTES", "720")),
        login_max_failures=_int("LOGIN_MAX_FAILURES", os.getenv("LOGIN_MAX_FAILURES", "5")),
        login_lock_minutes=_int("LOGIN_LOCK_MINUTES", os.getenv("LOGIN_LOCK_MINUTES", "15")),
        password_min_length=_int("PASSWORD_MIN_LENGTH", os.getenv("PASSWORD_MIN_LENGTH", "14")),
    )
    settings.validate()
    return settings
