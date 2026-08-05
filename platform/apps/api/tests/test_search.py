from fastapi.testclient import TestClient

from aisearcharab_api.arabic import normalize_text, protected_entities_in, tokenize
from aisearcharab_api.models import ContentItem
from aisearcharab_api.search import rank_item


def test_arabic_normalization_is_conservative() -> None:
    assert normalize_text("إستخدامُ الذكاءِ الاصطناعي") == "استخدام الذكاء الاصطناعي"
    assert normalize_text("على") == "علي"
    assert "ة" in normalize_text("أداة")


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
