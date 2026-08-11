from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .database import get_db
from .models import AdminSession, User
from .rbac import authorize, permissions_for_role
from .security import secret_digest

PRIVILEGED_MFA_ROLES = frozenset({"owner", "admin", "publisher"})


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class Principal:
    user: User
    session: AdminSession
    permissions: frozenset[str]


def mfa_required_for_user(request: Request, user: User) -> bool:
    settings = request.app.state.settings
    return user.mfa_enabled_at is not None or (
        settings.require_mfa_for_privileged and user.role in PRIVILEGED_MFA_ROLES
    )


def get_base_principal(request: Request, db: Annotated[Session, Depends(get_db)]) -> Principal:
    """Authenticate the opaque session without requiring completion of MFA.

    This dependency is intentionally restricted to MFA enrollment/verification and
    session termination paths. Application/admin authorization must use get_principal.
    """
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    statement = (
        select(AdminSession)
        .where(AdminSession.token_hash == secret_digest(token), AdminSession.revoked_at.is_(None))
        .options(selectinload(AdminSession.user))
    )
    admin_session = db.scalar(statement)
    now = datetime.now(timezone.utc)
    if admin_session is None or not admin_session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    if _aware(admin_session.expires_at) <= now:
        admin_session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    idle_deadline = _aware(admin_session.last_seen_at) + timedelta(minutes=settings.session_idle_minutes)
    if idle_deadline <= now:
        admin_session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    if _aware(admin_session.last_seen_at) + timedelta(minutes=5) <= now:
        admin_session.last_seen_at = now
        db.commit()

    return Principal(
        user=admin_session.user,
        session=admin_session,
        permissions=permissions_for_role(admin_session.user.role),
    )


def get_principal(
    request: Request,
    principal: Annotated[Principal, Depends(get_base_principal)],
) -> Principal:
    if mfa_required_for_user(request, principal.user) and principal.session.mfa_verified_at is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="multi-factor authentication required")
    return principal


def _check_permissions(principal: Principal, required: tuple[str, ...]) -> None:
    decision = authorize(principal.user.role, required)
    if not decision.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")


def _check_csrf(request: Request, principal: Principal) -> None:
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(secret_digest(supplied), principal.session.csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf validation failed")


def require_step_up(principal: Principal) -> Principal:
    elevated_until = principal.session.elevated_until
    if elevated_until is None or _aware(elevated_until) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="step-up authentication required")
    return principal


def require_permissions(*required: str):
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        _check_permissions(principal, tuple(required))
        return principal

    return dependency


def require_csrf(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    _check_csrf(request, principal)
    return principal


def require_base_csrf(request: Request, principal: Annotated[Principal, Depends(get_base_principal)]) -> Principal:
    _check_csrf(request, principal)
    return principal


def require_mutation(*required: str):
    def dependency(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        _check_permissions(principal, tuple(required))
        _check_csrf(request, principal)
        return principal

    return dependency


def require_sensitive_mutation(*required: str):
    def dependency(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        _check_permissions(principal, tuple(required))
        _check_csrf(request, principal)
        return require_step_up(principal)

    return dependency
