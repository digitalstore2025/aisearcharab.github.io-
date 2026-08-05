import hashlib

from aisearcharab_api.models import SearchQueryEvent
from aisearcharab_api.privacy import hash_query


def test_search_analytics_schema_does_not_store_plaintext_queries() -> None:
    columns = set(SearchQueryEvent.__table__.columns.keys())
    assert "query" not in columns
    assert "normalized_query" not in columns
    assert "query_hash" in columns


def test_query_hash_is_keyed_and_not_plain_sha256() -> None:
    query = "الذكاء الاصطناعي"
    key = "a-secure-test-key-with-more-than-32-bytes"
    digest = hash_query(query, key)
    assert len(digest) == 64
    assert digest != hashlib.sha256(query.encode("utf-8")).hexdigest()
    assert digest != hash_query(query, "another-secure-key-with-more-than-32-bytes")
