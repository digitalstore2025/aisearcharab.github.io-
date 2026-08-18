import io
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aisearcharab_api.geo.evidence_store import append_provider_result
from aisearcharab_api.geo.providers.base import ProviderResult
from aisearcharab_api.geo.providers.ollama import OllamaProvider
from aisearcharab_api.geo.query_routes import QuerySetCreate
from aisearcharab_api.geo.schemas import GeoProjectCreate, OrganizationCreate


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._payload.read(size)


@pytest.mark.parametrize(
    "factory, payload",
    [
        (OrganizationCreate, {"slug": "org", "name": "   "}),
        (GeoProjectCreate, {"slug": "project", "name": "   ", "domain": "example.com"}),
        (QuerySetCreate, {"slug": "queries", "name": "   "}),
    ],
)
def test_display_names_are_validated_after_normalization(factory, payload) -> None:
    with pytest.raises(ValidationError):
        factory(**payload)


def test_ollama_locale_is_explicit_and_wire_payload_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b'{  "model": "local", "message": {"role": "assistant", "content": "Merhaba"}, "done": true }\n'

    def fake_open(request, *, timeout):
        body = json.loads(request.data.decode("utf-8"))
        system_prompt = body["messages"][0]["content"]
        assert "Turkish (tr)" in system_prompt
        return _FakeResponse(raw)

    monkeypatch.setattr("aisearcharab_api.geo.providers.ollama._open_no_redirect", fake_open)
    result = OllamaProvider(model="local").run_query("Merhaba", locale="tr")
    assert result.raw_payload == raw.decode("utf-8")
    assert result.answer_text == "Merhaba"


def test_evidence_helper_does_not_commit_caller_transaction() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.added = []
            self.flush_count = 0
            self.commit_called = False

        def scalar(self, statement):
            return SimpleNamespace(id="query-1", text="hello")

        def add(self, item) -> None:
            self.added.append(item)

        def flush(self) -> None:
            self.flush_count += 1

        def refresh(self, item) -> None:
            return None

        def commit(self) -> None:
            self.commit_called = True
            raise AssertionError("append_provider_result must not commit caller-owned transaction")

    db = FakeSession()
    result = ProviderResult(
        provider="provider",
        model="model",
        query="hello",
        answer_text="answer",
        citations=(),
        mentions=(),
        raw_payload='{"answer":"answer"}',
    )
    run = append_provider_result(
        db,  # type: ignore[arg-type]
        organization_id="org-1",
        project_id="project-1",
        query_id="query-1",
        result=result,
    )
    assert run.query_id == "query-1"
    assert db.flush_count >= 2
    assert db.commit_called is False
