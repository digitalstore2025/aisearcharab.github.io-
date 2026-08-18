import io
import json
import urllib.error

import pytest

from aisearcharab_api.geo.providers.ollama import OllamaProvider, OllamaProviderError


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._payload.read(size)


def test_ollama_provider_returns_normalized_result_without_fabricated_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {
        "model": "local-model:latest",
        "message": {"role": "assistant", "content": "إجابة محلية"},
        "done": True,
    }

    def fake_open(request, *, timeout):
        assert request.full_url == "http://ollama:11434/api/chat"
        assert timeout == 30
        body = json.loads(request.data.decode("utf-8"))
        assert body["stream"] is False
        assert body["messages"][-1]["content"] == "ما هو الذكاء الاصطناعي؟"
        return _FakeResponse(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    monkeypatch.setattr("aisearcharab_api.geo.providers.ollama._open_no_redirect", fake_open)
    provider = OllamaProvider(model="local-model:latest", timeout_seconds=30)
    result = provider.run_query("  ما هو الذكاء الاصطناعي؟  ", locale="ar")

    assert result.provider == "ollama"
    assert result.model == "local-model:latest"
    assert result.query == "ما هو الذكاء الاصطناعي؟"
    assert result.answer_text == "إجابة محلية"
    assert result.citations == ()
    assert result.mentions == ()
    assert json.loads(result.raw_payload)["done"] is True
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_ollama_provider_rejects_non_allowlisted_endpoint() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        OllamaProvider(model="model", base_url="http://169.254.169.254:11434")


def test_ollama_provider_rejects_non_allowlisted_local_port() -> None:
    with pytest.raises(ValueError, match="port is not allowlisted"):
        OllamaProvider(model="model", base_url="http://127.0.0.1:22")
    with pytest.raises(ValueError, match="port is not allowlisted"):
        OllamaProvider(model="model", base_url="http://localhost:8000")


def test_ollama_provider_rejects_credentials_and_paths() -> None:
    with pytest.raises(ValueError, match="credentials"):
        OllamaProvider(model="model", base_url="http://user:pass@localhost:11434")
    with pytest.raises(ValueError, match="must not include a path"):
        OllamaProvider(model="model", base_url="http://localhost:11434/api")


def test_ollama_provider_fails_closed_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_open(request, *, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("aisearcharab_api.geo.providers.ollama._open_no_redirect", fake_open)
    provider = OllamaProvider(model="model")
    with pytest.raises(OllamaProviderError, match="request failed"):
        provider.run_query("hello", locale="en")


def test_ollama_provider_fails_closed_on_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_open(request, *, timeout):
        raise urllib.error.HTTPError(
            "http://169.254.169.254/latest/meta-data/",
            302,
            "Ollama redirects are forbidden",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("aisearcharab_api.geo.providers.ollama._open_no_redirect", fake_open)
    provider = OllamaProvider(model="model")
    with pytest.raises(OllamaProviderError, match="request failed"):
        provider.run_query("hello", locale="en")


def test_ollama_provider_fails_closed_on_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aisearcharab_api.geo.providers.ollama._open_no_redirect",
        lambda request, *, timeout: _FakeResponse(b"not-json"),
    )
    provider = OllamaProvider(model="model")
    with pytest.raises(OllamaProviderError, match="invalid JSON"):
        provider.run_query("hello", locale="en")


def test_ollama_provider_rejects_unsupported_locale() -> None:
    provider = OllamaProvider(model="model")
    with pytest.raises(ValueError, match="locale"):
        provider.run_query("hello", locale="fr")


def test_ollama_provider_rejects_non_string_query_and_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be numeric"):
        OllamaProvider(model="model", timeout_seconds=True)
    provider = OllamaProvider(model="model")
    with pytest.raises(ValueError, match="query must be a string"):
        provider.run_query(123, locale="en")  # type: ignore[arg-type]
