from fastapi.testclient import TestClient

from aisearcharab_api.arabic import normalize_text, protected_entities_in, tokenize
from aisearcharab_api.database import get_db
from aisearcharab_api.main import BOUNDED_LOAD_EVIDENCE_MARKER, create_app
from aisearcharab_api.models import ContentItem, SearchQueryEvent
from aisearcharab_api.search import rank_item


def test_arabic_normalization_is_conservative() -> None:
    assert normalize_text("إستخدامُ الذكاءِ الاصطناعي") == "استخدام الذكاء الاصطناعي"
    assert normalize_text("على") == "علي"
    assert "ة" in normalize_text("أداة")


def test_arabic_normalization_removes_invisible_format_controls() -> None:
    assert normalize_text("الذ\u200bكاء") == "الذكاء"
    assert normalize_text("\u2067إستخدام\u2069") == "استخدام"
    assert normalize_text("\u061cالذكاء") == "الذكاء"
    assert tokenize("Open\u202eAI API") == ("openai", "api")
    assert tokenize("Open\ufeffAI API") == ("openai", "api")


def test_tokenizer_preserves_technical_tokens() -> None:
    assert "gpt-5" in tokenize("تحليل GPT-5")
    assert protected_entities_in("OpenAI API وGitHub") == ("openai api", "github")


def test_search_ranks_protected_entity_first(client: TestClient) -> None:
    response = client.get("/v1/search", params={"q": "GPT-5"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_mode"] == "retrieval-only"
    assert payload["algorithm_version"] == "lexical-v1"
    assert payload["results"][0]["slug"] == "gpt-5-arabic-analysis"
    assert "answer" not in payload


def test_search_handles_arabic_without_diacritics(client: TestClient) -> None:
    response = client.get("/v1/search", params={"q": "الذَّكاء الاصطناعي للأطفال"})
    assert response.status_code == 200
    assert response.json()["results"][0]["slug"] == "ai-children-safety"


def test_draft_is_not_returned(client: TestClient) -> None:
    response = client.get("/v1/search", params={"q": "مسودة غير منشورة"})
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_search_limit_is_enforced(client: TestClient) -> None:
    response = client.get("/v1/search", params={"q": "الذكاء", "limit": 21})
    assert response.status_code == 400


def test_query_length_is_validated(client: TestClient) -> None:
    response = client.get("/v1/search", params={"q": "ا"})
    assert response.status_code == 422


def test_bounded_staging_load_search_suppresses_query_log_write(session_factory, settings) -> None:
    staging_settings = settings.model_copy(
        update={
            "environment": "staging",
            "log_queries": True,
            "query_hash_key": "staging-load-evidence-test-key",
        }
    )
    app = create_app(staging_settings)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        normal = test_client.get("/v1/search", params={"q": "GPT-5"})
        assert normal.status_code == 200
        with session_factory() as session:
            assert session.query(SearchQueryEvent).count() == 1

        evidence = test_client.get(
            "/v1/search",
            params={"q": "GPT-5", "_evidence": BOUNDED_LOAD_EVIDENCE_MARKER},
        )
        assert evidence.status_code == 200
        with session_factory() as session:
            assert session.query(SearchQueryEvent).count() == 1


def test_load_evidence_marker_does_not_bypass_logging_outside_staging(session_factory, settings) -> None:
    test_settings = settings.model_copy(
        update={
            "environment": "test",
            "log_queries": True,
            "query_hash_key": "load-evidence-boundary-test-key",
        }
    )
    app = create_app(test_settings)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        response = test_client.get(
            "/v1/search",
            params={"q": "GPT-5", "_evidence": BOUNDED_LOAD_EVIDENCE_MARKER},
        )
        assert response.status_code == 200
        with session_factory() as session:
            assert session.query(SearchQueryEvent).count() == 1


def test_short_latin_token_does_not_match_inside_unrelated_word() -> None:
    item = ContentItem(
        slug="unrelated",
        title="Said and reported",
        summary="No matching technical term is present.",
        body="Editorial copy only.",
        section="news",
        language="en",
        status="published",
        is_indexed=True,
        source_authority=5.0,
    )
    assert rank_item("ai", item) is None