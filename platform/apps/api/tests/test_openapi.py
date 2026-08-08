from aisearcharab_api.config import Settings
from aisearcharab_api.main import create_app


FORBIDDEN_CAPABILITY_PREFIXES = (
    "/v1/rag",
    "/v1/generate",
    "/v1/generated",
    "/v1/answers",
    "/v1/payment",
    "/v1/payments",
    "/v1/checkout",
    "/v1/subscription",
    "/v1/subscriptions",
    "/v1/crawl",
    "/v1/crawler",
)


def test_openapi_exposes_only_approved_platform_capabilities() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:3000",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
    )
    paths = set(create_app(settings).openapi()["paths"])
    assert "/v1/search" in paths
    assert "/v1/meta/capabilities" in paths
    assert "/v1/auth/mfa/recovery-codes/regenerate" in paths
    assert not any(
        path == prefix or path.startswith(f"{prefix}/")
        for path in paths
        for prefix in FORBIDDEN_CAPABILITY_PREFIXES
    )
