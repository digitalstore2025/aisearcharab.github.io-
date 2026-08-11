import json

import pytest

from scripts.load_probe import load_queries, percentile, summarize, validate_base_url


def test_percentile_uses_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 50) == 30.0
    assert percentile(values, 95) == 50.0
    assert percentile([], 95) == 0.0


def test_summary_reports_aggregate_metrics_only() -> None:
    summary = summarize([20.0, 10.0, 40.0, 30.0], requests=5, errors=1)
    assert summary.requests == 5
    assert summary.successes == 4
    assert summary.errors == 1
    assert summary.error_rate == 0.2
    assert summary.p50_ms == 20.0
    assert summary.p95_ms == 40.0
    assert summary.p99_ms == 40.0
    assert summary.min_ms == 10.0
    assert summary.max_ms == 40.0


def test_load_queries_supports_string_and_object_rows(tmp_path) -> None:
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps(["الذكاء الاصطناعي", {"query": "نماذج اللغة العربية"}], ensure_ascii=False),
        encoding="utf-8",
    )
    assert load_queries(path) == ["الذكاء الاصطناعي", "نماذج اللغة العربية"]


def test_load_queries_rejects_invalid_or_empty_rows(tmp_path) -> None:
    path = tmp_path / "queries.json"
    path.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_queries(path)

    path.write_text(json.dumps([{"not_query": "x"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_queries(path)


def test_base_url_requires_https_and_rejects_credentials() -> None:
    assert validate_base_url("https://staging.example/api/", allow_http=False) == "https://staging.example/api"
    with pytest.raises(ValueError):
        validate_base_url("http://staging.example", allow_http=False)
    with pytest.raises(ValueError):
        validate_base_url("https://user:secret@staging.example", allow_http=False)
    assert validate_base_url("http://127.0.0.1:8000", allow_http=True) == "http://127.0.0.1:8000"
