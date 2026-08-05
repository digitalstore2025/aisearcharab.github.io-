from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import Principal, get_principal, require_csrf
from .database import get_db
from .models import AdminSession, User
from .rbac import permissions_for_role
from .schemas import LoginRequest, LoginResponse, UserPublic
from .security import new_secret, normalize_email, perform_dummy_password_check, secret_digest, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def user_public(user: User) -> UserPublic:
    return UserPublic.model_validate(
        {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": user.is_active,
            "permissions": sorted(permissions_for_role(user.role)),
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        }
    )


def _set_auth_cookies(response: Response, request: Request, session_token: str, csrf_token: str, max_age: int) -> None:
    settings = request.app.state.settings
    common = {
        "max_age": max_age,
        "path": "/",
        "secure": settings.secure_cookies,
        "samesite": "strict",
    }
    response.set_cookie(settings.session_cookie_name, session_token, httponly=True, **common)
    response.set_cookie(settings.csrf_cookie_name, csrf_token, httponly=False, **common)


def _clear_auth_cookies(response: Response, request: Request) -> None:
    settings = request.app.state.settings
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.secure_cookies, samesite="strict")
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.secure_cookies, samesite="strict")


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    settings = request.app.state.settings
    try:
        email = normalize_email(payload.email)
    except ValueError:
        perform_dummy_password_check(payload.password)
        time.sleep(0.08)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    user = db.scalar(select(User).where(User.email == email))
    now = datetime.now(timezone.utc)
    locked = user is not None and user.locked_until is not None and (user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)) > now
    valid = user is not None and user.is_active and not locked and verify_password(payload.password, user.password_hash)

    if not valid:
        if user is None:
            perform_dummy_password_check(payload.password)
        elif not locked:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_failures:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_count = 0
        record_audit(
            db,
            action="auth.login",
            outcome="failure",
            actor_user_id=user.id if user else None,
            target_type="user",
            target_id=user.id if user else None,
            request_id=getattr(request.state, "request_id", None),
            metadata={"reason": "invalid_credentials"},
        )
        db.commit()
        time.sleep(0.08)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    session_token = new_secret()
    csrf_token = new_secret()
    expires_at = now + timedelta(minutes=settings.session_ttl_minutes)
    db.add(
        AdminSession(
            user_id=user.id,
            token_hash=secret_digest(session_token),
            csrf_hash=secret_digest(csrf_token),
            expires_at=expires_at,
        )
    )
    record_audit(
        db,
        action="auth.login",
        outcome="success",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    _set_auth_cookies(response, request, session_token, csrf_token, settings.session_ttl_minutes * 60)
    return LoginResponse(user=user_public(user), expires_at=expires_at)


@router.get("/me", response_model=UserPublic)
def me(principal: Annotated[Principal, Depends(get_principal)]) -> UserPublic:
    return user_public(principal.user)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    principal.session.revoked_at = datetime.now(timezone.utc)
    record_audit(
        db,
        action="auth.logout",
        outcome="success",
        actor_user_id=principal.user.id,
        target_type="session",
        target_id=principal.session.id,
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    _clear_auth_cookies(response, request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
