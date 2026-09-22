import pytest
from pydantic import ValidationError

from aisearcharab_api.schemas import ContentCreate, ContentUpdate, SearchResult


CONTENT_PAYLOAD = {
    "slug": "safe-path-test",
    "title": "Canonical URL path validation",
    "summary": "A sufficiently long summary used for schema security regression coverage.",
    "body": "A sufficiently long body used to verify URL path validation at the API trust boundary.",
    "section": "reports",
    "language": "en",
    "source_authority": 5.0,
}


BAD_PATHS = [
    r"/\evil.example",
    "//evil.example",
    "/%5cevil.example",
    "/%2f%2fevil.example",
    "/reports/item?next=evil",
    "/reports/item#fragment",
    "/reports/\x00item",
]


@pytest.mark.parametrize("bad_path", BAD_PATHS)
def test_content_mutation_models_reject_noncanonical_or_cross_origin_paths(bad_path: str) -> None:
    with pytest.raises(ValidationError):
        ContentCreate(url_path=bad_path, **CONTENT_PAYLOAD)
    with pytest.raises(ValidationError):
        ContentUpdate(url_path=bad_path)


@pytest.mark.parametrize("bad_path", BAD_PATHS)
def test_search_result_fails_closed_for_unsafe_legacy_paths(bad_path: str) -> None:
    with pytest.raises(ValidationError):
        SearchResult(
            slug="safe-path-test",
            url=bad_path,
            title="Safe title",
            summary="Safe summary",
            section="reports",
            language="en",
            published_at=None,
            score=1.0,
            matched_fields=["title"],
            source_authority=5.0,
        )


def test_canonical_local_path_remains_valid() -> None:
    created = ContentCreate(url_path="/reports/safe-path-test/", **CONTENT_PAYLOAD)
    assert created.url_path == "/reports/safe-path-test/"
