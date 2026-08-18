from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import Principal
from .models import OrganizationMembership

ORG_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({"geo:read", "geo:write", "geo:manage_members", "geo:manage_org"}),
    "admin": frozenset({"geo:read", "geo:write", "geo:manage_members"}),
    "analyst": frozenset({"geo:read", "geo:write"}),
    "viewer": frozenset({"geo:read"}),
}


@dataclass(frozen=True, slots=True)
class TenantAccess:
    organization_id: str
    membership: OrganizationMembership
    permissions: frozenset[str]


def require_tenant_access(
    db: Session,
    principal: Principal,
    organization_id: str,
    *required: str,
) -> TenantAccess:
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == principal.user.id,
        )
    )
    # Deliberately return 404 for cross-tenant access to avoid confirming that
    # another organization's identifier exists.
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")
    permissions = ORG_ROLE_PERMISSIONS.get(membership.role, frozenset())
    if any(permission not in permissions for permission in required):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient organization permissions")
    return TenantAccess(
        organization_id=organization_id,
        membership=membership,
        permissions=permissions,
    )
