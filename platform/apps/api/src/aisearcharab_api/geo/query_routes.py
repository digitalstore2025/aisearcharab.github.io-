from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..auth import Principal, get_principal, require_csrf
from ..database import get_db
from .evidence_models import GeoQuery, QuerySet
from .models import GeoProject
from .tenant import require_tenant_access

router = APIRouter(tags=["geo-queries"])
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class QuerySetCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SLUG.fullmatch(normalized):
            raise ValueError("invalid slug")
        return normalized

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("name must be a string")
        return value.strip()


class QuerySetPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    project_id: str
    slug: str
    name: str
    created_at: datetime


class QueryCreate(BaseModel):
    text: str = Field(min_length=2, max_length=2000)
    language: str = Field(default="ar")

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("query is too short")
        return normalized

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"ar", "en", "tr"}:
            raise ValueError("unsupported query language")
        return normalized


class QueryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    project_id: str
    query_set_id: str
    text: str
    language: str
    is_active: bool
    created_at: datetime


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _project(db: Session, organization_id: str, project_id: str) -> GeoProject:
    item = db.scalar(
        select(GeoProject).where(
            GeoProject.id == project_id,
            GeoProject.organization_id == organization_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="project not found")
    return item


def _query_set(db: Session, organization_id: str, project_id: str, query_set_id: str) -> QuerySet:
    item = db.scalar(
        select(QuerySet).where(
            QuerySet.id == query_set_id,
            QuerySet.organization_id == organization_id,
            QuerySet.project_id == project_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="query set not found")
    return item


@router.get(
    "/organizations/{organization_id}/projects/{project_id}/query-sets",
    response_model=list[QuerySetPublic],
)
def list_query_sets(
    organization_id: str,
    project_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[QuerySetPublic]:
    require_tenant_access(db, principal, organization_id, "geo:read")
    _project(db, organization_id, project_id)
    rows = db.scalars(
        select(QuerySet).where(
            QuerySet.organization_id == organization_id,
            QuerySet.project_id == project_id,
        ).order_by(QuerySet.created_at.asc())
    ).all()
    return [QuerySetPublic.model_validate(row) for row in rows]


@router.post(
    "/organizations/{organization_id}/projects/{project_id}/query-sets",
    response_model=QuerySetPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_query_set(
    organization_id: str,
    project_id: str,
    payload: QuerySetCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> QuerySetPublic:
    require_tenant_access(db, principal, organization_id, "geo:write")
    _project(db, organization_id, project_id)
    row = QuerySet(
        organization_id=organization_id,
        project_id=project_id,
        slug=payload.slug,
        name=payload.name,
        created_by_user_id=principal.user.id,
    )
    db.add(row)
    try:
        db.flush()
        record_audit(
            db,
            action="geo.query_set.create",
            outcome="success",
            actor_user_id=principal.user.id,
            target_type="geo_query_set",
            target_id=row.id,
            request_id=_rid(request),
            metadata={"organization_id": organization_id, "project_id": project_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="query set slug already exists in project") from exc
    db.refresh(row)
    return QuerySetPublic.model_validate(row)


@router.get(
    "/organizations/{organization_id}/projects/{project_id}/query-sets/{query_set_id}/queries",
    response_model=list[QueryPublic],
)
def list_queries(
    organization_id: str,
    project_id: str,
    query_set_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[QueryPublic]:
    require_tenant_access(db, principal, organization_id, "geo:read")
    _project(db, organization_id, project_id)
    _query_set(db, organization_id, project_id, query_set_id)
    rows = db.scalars(
        select(GeoQuery).where(
            GeoQuery.organization_id == organization_id,
            GeoQuery.project_id == project_id,
            GeoQuery.query_set_id == query_set_id,
        ).order_by(GeoQuery.created_at.asc())
    ).all()
    return [QueryPublic.model_validate(row) for row in rows]


@router.post(
    "/organizations/{organization_id}/projects/{project_id}/query-sets/{query_set_id}/queries",
    response_model=QueryPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_query(
    organization_id: str,
    project_id: str,
    query_set_id: str,
    payload: QueryCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> QueryPublic:
    require_tenant_access(db, principal, organization_id, "geo:write")
    _project(db, organization_id, project_id)
    _query_set(db, organization_id, project_id, query_set_id)
    row = GeoQuery(
        organization_id=organization_id,
        project_id=project_id,
        query_set_id=query_set_id,
        text=payload.text,
        language=payload.language,
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="geo.query.create",
        outcome="success",
        actor_user_id=principal.user.id,
        target_type="geo_query",
        target_id=row.id,
        request_id=_rid(request),
        metadata={"organization_id": organization_id, "project_id": project_id, "language": row.language},
    )
    db.commit()
    db.refresh(row)
    return QueryPublic.model_validate(row)
