from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from aisearcharab_api.geo import query_routes
from aisearcharab_api.geo.query_routes import QueryCreate, create_query


def test_create_query_rolls_back_integrity_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.rollback_called = False
            self.commit_called = False

        def add(self, item) -> None:
            return None

        def flush(self) -> None:
            raise IntegrityError("forced query constraint failure", None, RuntimeError("constraint"))

        def rollback(self) -> None:
            self.rollback_called = True

        def commit(self) -> None:
            self.commit_called = True

        def refresh(self, item) -> None:
            return None

    db = FakeSession()
    monkeypatch.setattr(query_routes, "require_tenant_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(query_routes, "_project", lambda *args, **kwargs: object())
    monkeypatch.setattr(query_routes, "_query_set", lambda *args, **kwargs: object())

    with pytest.raises(HTTPException) as raised:
        create_query(
            organization_id="org-1",
            project_id="project-1",
            query_set_id="set-1",
            payload=QueryCreate(text="query text", language="en"),
            request=SimpleNamespace(state=SimpleNamespace(request_id="request-1")),  # type: ignore[arg-type]
            principal=SimpleNamespace(user=SimpleNamespace(id="user-1")),  # type: ignore[arg-type]
            db=db,  # type: ignore[arg-type]
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == "query could not be created due to a constraint conflict"
    assert db.rollback_called is True
    assert db.commit_called is False