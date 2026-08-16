from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..auth import Principal, get_principal, require_csrf
from ..database import get_db
from .models import GeoProject, Organization, OrganizationMembership
from .schemas import GeoProjectCreate, GeoProjectPublic, OrganizationCreate, OrganizationPublic
from .tenant import require_tenant_access

router = APIRouter(prefix="/geo", tags=["geo"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/organizations", response_model=list[OrganizationPublic])
def list_organizations(
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[OrganizationPublic]:
    stmt = (
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == principal.user.id)
        .order_by(Organization.created_at.asc())
    )
    return [OrganizationPublic.model_validate(item) for item in db.scalars(stmt).all()]


@router.post("/organizations", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationPublic:
    organization = Organization(
        slug=payload.slug,
        name=payload.name.strip(),
        created_by_user_id=principal.user.id,
    )
    db.add(organization)
    try:
        db.flush()
        db.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=principal.user.id,
                role="owner",
            )
        )
        record_audit(
            db,
            action="geo.organization.create",
            outcome="success",
            actor_user_id=principal.user.id,
            target_type="organization",
            target_id=organization.id,
            request_id=_request_id(request),
            metadata={"slug": organization.slug},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="organization slug already exists") from exc
    db.refresh(organization)
    return OrganizationPublic.model_validate(organization)


@router.get("/organizations/{organization_id}/projects", response_model=list[GeoProjectPublic])
def list_projects(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[GeoProjectPublic]:
    require_tenant_access(db, principal, organization_id, "geo:read")
    items = db.scalars(
        select(GeoProject)
        .where(GeoProject.organization_id == organization_id)
        .order_by(GeoProject.created_at.asc())
    ).all()
    return [GeoProjectPublic.model_validate(item) for item in items]


@router.post(
    "/organizations/{organization_id}/projects",
    response_model=GeoProjectPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    organization_id: str,
    payload: GeoProjectCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> GeoProjectPublic:
    require_tenant_access(db, principal, organization_id, "geo:write")
    project = GeoProject(
        organization_id=organization_id,
        slug=payload.slug,
        name=payload.name.strip(),
        domain=payload.domain,
        created_by_user_id=principal.user.id,
    )
    db.add(project)
    try:
        db.flush()
        record_audit(
            db,
            action="geo.project.create",
            outcome="success",
            actor_user_id=principal.user.id,
            target_type="geo_project",
            target_id=project.id,
            request_id=_request_id(request),
            metadata={"organization_id": organization_id, "domain": project.domain},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="project slug already exists in organization") from exc
    db.refresh(project)
    return GeoProjectPublic.model_validate(project)
