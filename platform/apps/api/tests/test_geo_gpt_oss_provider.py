import json

import pytest

from aisearcharab_api.geo.providers.gpt_oss import (
    GPT_OSS_120B,
    GPT_OSS_20B,
    GptOssOllamaProvider,
)


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self._payload
        return self._payload[:size]


def test_gpt_oss_provider_defaults_to_20b_and_reports_capabilities() -> None:
    provider = GptOssOllamaProvider()

    assert provider.model == GPT_OSS_20B
    assert provider.name == "gpt-oss-ollama"
    assert provider.capabilities() == (
        "local-inference",
        "open-weight",
        "gpt-oss",
        "reasoning",
        "no-native-citations",
    )


def test_gpt_oss_provider_accepts_official_120b_identifier() -> None:
    provider = GptOssOllamaProvider(model=GPT_OSS_120B)
    assert provider.model == GPT_OSS_120B


def test_gpt_oss_provider_rejects_non_gpt_oss_model() -> None:
    with pytest.raises(ValueError, match="gpt-oss model must be one of"):
        GptOssOllamaProvider(model="llama3.2:latest")


def test_gpt_oss_provider_uses_hardened_ollama_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {
        "model": GPT_OSS_20B,
        "message": {"role": "assistant", "content": "إجابة محلية موثقة كاستجابة خام"},
        "done": True,
    }

    def fake_open(request, *, timeout):
        assert request.full_url == "http://ollama:11434/api/chat"
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["model"] == GPT_OSS_20B
        assert payload["stream"] is False
        assert payload["messages"][0]["role"] == "system"
        assert "Do not invent citations" in payload["messages"][0]["content"]
        assert payload["messages"][1]["content"] == "اختبر النموذج"
        return _FakeResponse(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    monkeypatch.setattr("aisearcharab_api.geo.providers.ollama._open_no_redirect", fake_open)

    result = GptOssOllamaProvider(timeout_seconds=30).run_query(" اختبر النموذج ", locale="ar")

    assert result.provider == "gpt-oss-ollama"
    assert result.model == GPT_OSS_20B
    assert result.query == "اختبر النموذج"
    assert result.answer_text == "إجابة محلية موثقة كاستجابة خام"
    assert result.citations == ()
    assert result.mentions == ()
    assert json.loads(result.raw_payload)["done"] is True
