from aisearcharab_api.config import Settings
from aisearcharab_api.main import create_app


def test_openapi_exposes_only_phase_two_capabilities() -> None:
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
    assert not any("payment" in path or "rag" in path or "generate" in path for path in paths)
