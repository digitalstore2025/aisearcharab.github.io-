from __future__ import annotations

import ipaddress
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


def _valid_host(value: str) -> bool:
    if not value or "://" in value or "/" in value or "@" in value:
        return False
    if value == "*":
        return True
    candidate = value[2:] if value.startswith("*.") else value
    return all(part and part.replace("-", "").isalnum() for part in candidate.split("."))


def _valid_proxy_cidr(value: str) -> bool:
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        return False
    return network.prefixlen > 0


def _proxy_cidrs_cover_entire_family(values: tuple[str, ...]) -> bool:
    networks = tuple(ipaddress.ip_network(value, strict=False) for value in values)
    for version in (4, 6):
        family = tuple(network for network in networks if network.version == version)
        if not family:
            continue
        collapsed = tuple(ipaddress.collapse_addresses(family))
        if len(collapsed) == 1 and collapsed[0].prefixlen == 0:
            return True
    return False


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    database_url: str
    allowed_origins: tuple[str, ...]
    api_prefix: str
    max_search_limit: int
    log_queries: bool
    query_hash_key: str | None = None
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    max_request_body_bytes: int = 524_288
    search_candidate_limit: int = 300
    session_ttl_minutes: int = 720
    session_idle_minutes: int = 30
    step_up_ttl_minutes: int = 10
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    login_throttle_key: str | None = None
    login_throttle_max_failures: int = 8
    login_throttle_window_seconds: int = 300
    login_throttle_block_seconds: int = 300
    trusted_proxy_cidrs: tuple[str, ...] = ()
    password_min_length: int = 14
    enforce_separation_of_duties: bool = False
    require_mfa_for_privileged: bool = False
    mfa_encryption_key: str | None = None
    mfa_enrollment_ttl_minutes: int = 10
    mfa_issuer: str = "AISearcharab.com"
    generated_answers_enabled: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_timeout_seconds: int = 20
    openai_max_retries: int = 2
    openai_max_output_tokens: int = 1200
    generated_answer_max_sources: int = 5
    generated_answer_max_evidence_chars: int = 6000
    generated_answer_max_requests: int = 20
    generated_answer_window_seconds: int = 3600

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
        secure_runtime = self.environment in {"staging", "production"}
        if not self.database_url:
            raise ConfigurationError("DATABASE_URL is required")
        if not self.api_prefix.startswith("/") or self.api_prefix == "/":
            raise ConfigurationError("API_PREFIX must start with '/' and include a version segment")
        if not 1 <= self.max_search_limit <= 100:
            raise ConfigurationError("MAX_SEARCH_LIMIT must be between 1 and 100")
        if not self.max_search_limit <= self.search_candidate_limit <= 2_000:
            raise ConfigurationError("SEARCH_CANDIDATE_LIMIT must be between MAX_SEARCH_LIMIT and 2000")
        if not 16_384 <= self.max_request_body_bytes <= 5_000_000:
            raise ConfigurationError("MAX_REQUEST_BODY_BYTES must be between 16384 and 5000000")
        if not self.allowed_hosts or any(not _valid_host(host) for host in self.allowed_hosts):
            raise ConfigurationError("ALLOWED_HOSTS must contain valid host names")
        if not 15 <= self.session_ttl_minutes <= 1440:
            raise ConfigurationError("SESSION_TTL_MINUTES must be between 15 and 1440")
        if not 5 <= self.session_idle_minutes <= 240:
            raise ConfigurationError("SESSION_IDLE_MINUTES must be between 5 and 240")
        if self.session_idle_minutes >= self.session_ttl_minutes:
            raise ConfigurationError("SESSION_IDLE_MINUTES must be lower than SESSION_TTL_MINUTES")
        if not 2 <= self.step_up_ttl_minutes <= 30:
            raise ConfigurationError("STEP_UP_TTL_MINUTES must be between 2 and 30")
        if self.step_up_ttl_minutes >= self.session_ttl_minutes:
            raise ConfigurationError("STEP_UP_TTL_MINUTES must be lower than SESSION_TTL_MINUTES")
        if not 3 <= self.login_max_failures <= 20:
            raise ConfigurationError("LOGIN_MAX_FAILURES must be between 3 and 20")
        if not 1 <= self.login_lock_minutes <= 1440:
            raise ConfigurationError("LOGIN_LOCK_MINUTES must be between 1 and 1440")
        if not 3 <= self.login_throttle_max_failures <= 100:
            raise ConfigurationError("LOGIN_THROTTLE_MAX_FAILURES must be between 3 and 100")
        if not 30 <= self.login_throttle_window_seconds <= 3600:
            raise ConfigurationError("LOGIN_THROTTLE_WINDOW_SECONDS must be between 30 and 3600")
        if not 30 <= self.login_throttle_block_seconds <= 3600:
            raise ConfigurationError("LOGIN_THROTTLE_BLOCK_SECONDS must be between 30 and 3600")
        if self.login_throttle_key is not None and len(self.login_throttle_key.encode("utf-8")) < 32:
            raise ConfigurationError("LOGIN_THROTTLE_KEY must contain at least 32 bytes")
        if any(not _valid_proxy_cidr(cidr) for cidr in self.trusted_proxy_cidrs):
            raise ConfigurationError("TRUSTED_PROXY_CIDRS must contain explicit IP networks and must not include /0")
        if self.trusted_proxy_cidrs and _proxy_cidrs_cover_entire_family(self.trusted_proxy_cidrs):
            raise ConfigurationError("TRUSTED_PROXY_CIDRS must not collectively trust an entire IP address family")
        if not 12 <= self.password_min_length <= 128:
            raise ConfigurationError("PASSWORD_MIN_LENGTH must be between 12 and 128")
        if not 2 <= self.mfa_enrollment_ttl_minutes <= 30:
            raise ConfigurationError("MFA_ENROLLMENT_TTL_MINUTES must be between 2 and 30")
        if not 2 <= len(self.mfa_issuer.strip()) <= 64:
            raise ConfigurationError("MFA_ISSUER must contain between 2 and 64 characters")
        if self.mfa_encryption_key is not None and len(self.mfa_encryption_key.encode("utf-8")) < 32:
            raise ConfigurationError("MFA_ENCRYPTION_KEY must contain at least 32 bytes")
        if self.require_mfa_for_privileged and not self.mfa_encryption_key:
            raise ConfigurationError("MFA_ENCRYPTION_KEY is required when privileged MFA is enabled")
        if not self.allowed_origins:
            raise ConfigurationError("ALLOWED_ORIGINS must contain at least one explicit origin")
        if any(not _valid_origin(origin, require_https=secure_runtime) for origin in self.allowed_origins):
            raise ConfigurationError(
                "ALLOWED_ORIGINS must contain valid origins without paths, credentials, queries, or fragments; "
                "staging and production origins must use HTTPS"
            )
        if self.log_queries and (self.query_hash_key is None or len(self.query_hash_key.encode("utf-8")) < 32):
            raise ConfigurationError("QUERY_HASH_KEY must contain at least 32 bytes when query logging is enabled")
        if not 5 <= self.openai_timeout_seconds <= 120:
            raise ConfigurationError("OPENAI_TIMEOUT_SECONDS must be between 5 and 120")
        if not 0 <= self.openai_max_retries <= 5:
            raise ConfigurationError("OPENAI_MAX_RETRIES must be between 0 and 5")
        if not 256 <= self.openai_max_output_tokens <= 4000:
            raise ConfigurationError("OPENAI_MAX_OUTPUT_TOKENS must be between 256 and 4000")
        if not 1 <= self.generated_answer_max_sources <= 8:
            raise ConfigurationError("GENERATED_ANSWER_MAX_SOURCES must be between 1 and 8")
        if not 500 <= self.generated_answer_max_evidence_chars <= 20_000:
            raise ConfigurationError("GENERATED_ANSWER_MAX_EVIDENCE_CHARS must be between 500 and 20000")
        if not 1 <= self.generated_answer_max_requests <= 1_000:
            raise ConfigurationError("GENERATED_ANSWER_MAX_REQUESTS must be between 1 and 1000")
        if not 60 <= self.generated_answer_window_seconds <= 86_400:
            raise ConfigurationError("GENERATED_ANSWER_WINDOW_SECONDS must be between 60 and 86400")
        if not 2 <= len(self.openai_model.strip()) <= 100:
            raise ConfigurationError("OPENAI_MODEL must contain between 2 and 100 characters")
        if self.generated_answers_enabled and not self.openai_api_key:
            raise ConfigurationError("OPENAI_API_KEY is required when generated answers are enabled")
        if secure_runtime:
            if not self.require_mfa_for_privileged:
                raise ConfigurationError("REQUIRE_MFA_FOR_PRIVILEGED must be enabled in staging and production")
            if not self.mfa_encryption_key:
                raise ConfigurationError("MFA_ENCRYPTION_KEY is required in staging and production")
            if not self.login_throttle_key:
                raise ConfigurationError("LOGIN_THROTTLE_KEY is required in staging and production")
            if self.database_url.startswith("sqlite"):
                raise ConfigurationError("SQLite is not allowed in staging or production")
            if any("*" in host for host in self.allowed_hosts):
                raise ConfigurationError("Wildcard hosts are not allowed in staging or production")
            if "change-me" in self.database_url.lower():
                raise ConfigurationError("DATABASE_URL contains a placeholder credential")
        if self.is_production:
            if self.generated_answers_enabled:
                raise ConfigurationError(
                    "Generated answers cannot be enabled in production until distributed rate limiting and observability are verified"
                )
            if "*" in self.allowed_origins:
                raise ConfigurationError("Wildcard CORS origins are not allowed in production")
            if not self.enforce_separation_of_duties:
                raise ConfigurationError("ENFORCE_SEPARATION_OF_DUTIES must be enabled in production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings(
        environment=os.getenv("APP_ENV", "development").strip().lower(),
        database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///./aisearcharab.db").strip(),
        allowed_origins=_csv(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")),
        allowed_hosts=_csv(os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")),
        api_prefix=os.getenv("API_PREFIX", "/v1").rstrip("/"),
        max_search_limit=_int("MAX_SEARCH_LIMIT", os.getenv("MAX_SEARCH_LIMIT", "20")),
        max_request_body_bytes=_int("MAX_REQUEST_BODY_BYTES", os.getenv("MAX_REQUEST_BODY_BYTES", "524288")),
        log_queries=_bool(os.getenv("LOG_SEARCH_QUERIES", "false")),
        query_hash_key=os.getenv("QUERY_HASH_KEY") or None,
        search_candidate_limit=_int("SEARCH_CANDIDATE_LIMIT", os.getenv("SEARCH_CANDIDATE_LIMIT", "300")),
        session_ttl_minutes=_int("SESSION_TTL_MINUTES", os.getenv("SESSION_TTL_MINUTES", "720")),
        session_idle_minutes=_int("SESSION_IDLE_MINUTES", os.getenv("SESSION_IDLE_MINUTES", "30")),
        step_up_ttl_minutes=_int("STEP_UP_TTL_MINUTES", os.getenv("STEP_UP_TTL_MINUTES", "10")),
        login_max_failures=_int("LOGIN_MAX_FAILURES", os.getenv("LOGIN_MAX_FAILURES", "5")),
        login_lock_minutes=_int("LOGIN_LOCK_MINUTES", os.getenv("LOGIN_LOCK_MINUTES", "15")),
        login_throttle_key=os.getenv("LOGIN_THROTTLE_KEY") or None,
        login_throttle_max_failures=_int("LOGIN_THROTTLE_MAX_FAILURES", os.getenv("LOGIN_THROTTLE_MAX_FAILURES", "8")),
        login_throttle_window_seconds=_int("LOGIN_THROTTLE_WINDOW_SECONDS", os.getenv("LOGIN_THROTTLE_WINDOW_SECONDS", "300")),
        login_throttle_block_seconds=_int("LOGIN_THROTTLE_BLOCK_SECONDS", os.getenv("LOGIN_THROTTLE_BLOCK_SECONDS", "300")),
        trusted_proxy_cidrs=_csv(os.getenv("TRUSTED_PROXY_CIDRS", "")),
        password_min_length=_int("PASSWORD_MIN_LENGTH", os.getenv("PASSWORD_MIN_LENGTH", "14")),
        enforce_separation_of_duties=_bool(os.getenv("ENFORCE_SEPARATION_OF_DUTIES", "false")),
        require_mfa_for_privileged=_bool(os.getenv("REQUIRE_MFA_FOR_PRIVILEGED", "false")),
        mfa_encryption_key=os.getenv("MFA_ENCRYPTION_KEY") or None,
        mfa_enrollment_ttl_minutes=_int("MFA_ENROLLMENT_TTL_MINUTES", os.getenv("MFA_ENROLLMENT_TTL_MINUTES", "10")),
        mfa_issuer=os.getenv("MFA_ISSUER", "AISearcharab.com").strip(),
        generated_answers_enabled=_bool(os.getenv("GENERATED_ANSWERS_ENABLED", "false")),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip(),
        openai_timeout_seconds=_int("OPENAI_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_SECONDS", "20")),
        openai_max_retries=_int("OPENAI_MAX_RETRIES", os.getenv("OPENAI_MAX_RETRIES", "2")),
        openai_max_output_tokens=_int("OPENAI_MAX_OUTPUT_TOKENS", os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1200")),
        generated_answer_max_sources=_int(
            "GENERATED_ANSWER_MAX_SOURCES", os.getenv("GENERATED_ANSWER_MAX_SOURCES", "5")
        ),
        generated_answer_max_evidence_chars=_int(
            "GENERATED_ANSWER_MAX_EVIDENCE_CHARS", os.getenv("GENERATED_ANSWER_MAX_EVIDENCE_CHARS", "6000")
        ),
        generated_answer_max_requests=_int(
            "GENERATED_ANSWER_MAX_REQUESTS", os.getenv("GENERATED_ANSWER_MAX_REQUESTS", "20")
        ),
        generated_answer_window_seconds=_int(
            "GENERATED_ANSWER_WINDOW_SECONDS", os.getenv("GENERATED_ANSWER_WINDOW_SECONDS", "3600")
        ),
    )
    settings.validate()
    return settings
