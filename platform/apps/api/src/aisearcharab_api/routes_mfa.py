from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import (
    PRIVILEGED_MFA_ROLES,
    Principal,
    mfa_required_for_user,
    require_base_csrf,
    require_sensitive_mutation,
)
from .database import get_db
from .mfa import (
    MfaSecretError,
    build_otpauth_uri,
    decrypt_totp_secret,
    encrypt_totp_secret,
    new_recovery_codes,
    new_totp_secret,
    recovery_code_digest,
    verify_totp,
)
from .models import AdminSession, MfaRecoveryCode, User
from .security import verify_password

router = APIRouter(prefix="/auth/mfa", tags=["auth", "mfa"])


class MfaStatusResponse(BaseModel):
    required: bool
    enrolled: bool
    verified: bool
    recovery_codes_remaining: int


class MfaEnrollmentStartRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class MfaEnrollmentStartResponse(BaseModel):
    secret: str
    otpauth_uri: str
    expires_at: datetime


class MfaEnrollmentConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class MfaEnrollmentConfirmResponse(BaseModel):
    verified_at: datetime
    recovery_codes: list[str]


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class MfaVerifyResponse(BaseModel):
    verified_at: datetime
    recovery_code_used: bool = False


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _master_key(request: Request) -> str:
    key = request.app.state.settings.mfa_encryption_key
    if not key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MFA service is not configured")
    return key


def _lock_user(db: Session, user_id: str) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return user


def _lock_session(db: Session, session_id: str) -> AdminSession:
    admin_session = db.scalar(
        select(AdminSession)
        .where(AdminSession.id == session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(timezone.utc)
    if (
        admin_session is None
        or admin_session.revoked_at is not None
        or _aware(admin_session.expires_at) <= now
    ):
        if admin_session is not None and admin_session.revoked_at is None:
            admin_session.revoked_at = now
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return admin_session


def _require_locked_step_up(admin_session: AdminSession) -> None:
    elevated_until = admin_session.elevated_until
    if elevated_until is None or _aware(elevated_until) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="step-up authentication required")


def _record_failed_factor(
    db: Session,
    request: Request,
    user: User,
    admin_session: AdminSession,
    action: str,
) -> None:
    settings = request.app.state.settings
    now = datetime.now(timezone.utc)
    user.failed_login_count += 1
    revoked = False
    if user.failed_login_count >= settings.login_max_failures:
        user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        user.failed_login_count = 0
        admin_session.revoked_at = now
        revoked = True
    record_audit(
        db,
        action=action,
        outcome="failure",
        actor_user_id=user.id,
        target_type="session",
        target_id=admin_session.id,
        request_id=_request_id(request),
        metadata={"reason": "invalid_factor", "session_revoked": revoked},
    )
    db.commit()
    time.sleep(0.08)


def _replace_recovery_codes(db: Session, user_id: str) -> list[str]:
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id))
    codes = new_recovery_codes(count=10)
    for code in codes:
        db.add(MfaRecoveryCode(user_id=user_id, code_hash=recovery_code_digest(code)))
    return codes


@router.get("/status", response_model=MfaStatusResponse)
def mfa_status(
    request: Request,
    principal: Annotated[Principal, Depends(require_base_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> MfaStatusResponse:
    remaining = db.scalar(
        select(func.count())
        .select_from(MfaRecoveryCode)
        .where(MfaRecoveryCode.user_id == principal.user.id, MfaRecoveryCode.used_at.is_(None))
    )
    return MfaStatusResponse(
        required=mfa_required_for_user(request, principal.user),
        enrolled=principal.user.mfa_enabled_at is not None and principal.user.mfa_secret_encrypted is not None,
        verified=principal.session.mfa_verified_at is not None,
        recovery_codes_remaining=int(remaining or 0),
    )


@router.post("/enroll/start", response_model=MfaEnrollmentStartResponse)
def start_enrollment(
    payload: MfaEnrollmentStartRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_base_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> MfaEnrollmentStartResponse:
    user = _lock_user(db, principal.user.id)
    admin_session = _lock_session(db, principal.session.id)
    if user.mfa_enabled_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA is already enrolled")
    if not verify_password(payload.password, user.password_hash):
        _record_failed_factor(db, request, user, admin_session, "auth.mfa.enroll_start")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    now = datetime.now(timezone.utc)
    settings = request.app.state.settings
    secret = new_totp_secret()
    expires_at = now + timedelta(minutes=settings.mfa_enrollment_ttl_minutes)
    user.mfa_pending_secret_encrypted = encrypt_totp_secret(secret, _master_key(request))
    user.mfa_pending_expires_at = expires_at
    record_audit(
        db,
        action="auth.mfa.enroll_start",
        outcome="success",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        request_id=_request_id(request),
        metadata={"expires_in_minutes": settings.mfa_enrollment_ttl_minutes},
    )
    db.commit()
    return MfaEnrollmentStartResponse(
        secret=secret,
        otpauth_uri=build_otpauth_uri(secret, account_name=user.email, issuer=settings.mfa_issuer),
        expires_at=expires_at,
    )


@router.post("/enroll/confirm", response_model=MfaEnrollmentConfirmResponse)
def confirm_enrollment(
    payload: MfaEnrollmentConfirmRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_base_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> MfaEnrollmentConfirmResponse:
    user = _lock_user(db, principal.user.id)
    admin_session = _lock_session(db, principal.session.id)
    now = datetime.now(timezone.utc)
    pending = user.mfa_pending_secret_encrypted
    pending_expires = user.mfa_pending_expires_at
    if not pending or not pending_expires:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA enrollment has not been started")
    if _aware(pending_expires) <= now:
        user.mfa_pending_secret_encrypted = None
        user.mfa_pending_expires_at = None
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA enrollment has expired")

    try:
        secret = decrypt_totp_secret(pending, _master_key(request))
    except MfaSecretError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MFA service is unavailable") from exc
    counter = verify_totp(secret, payload.code, last_counter=-1, now=now)
    if counter is None:
        _record_failed_factor(db, request, user, admin_session, "auth.mfa.enroll_confirm")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication code")

    recovery_codes = _replace_recovery_codes(db, user.id)
    user.mfa_secret_encrypted = pending
    user.mfa_pending_secret_encrypted = None
    user.mfa_pending_expires_at = None
    user.mfa_enabled_at = now
    user.mfa_last_counter = counter
    user.failed_login_count = 0
    user.locked_until = None
    admin_session.mfa_verified_at = now
    record_audit(
        db,
        action="auth.mfa.enroll_confirm",
        outcome="success",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        request_id=_request_id(request),
        metadata={"recovery_code_count": len(recovery_codes)},
    )
    db.commit()
    return MfaEnrollmentConfirmResponse(verified_at=now, recovery_codes=recovery_codes)


@router.post("/verify", response_model=MfaVerifyResponse)
def verify_factor(
    payload: MfaVerifyRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_base_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> MfaVerifyResponse:
    # The user lock serialises counter checks and recovery-code consumption for one
    # account across replicas backed by PostgreSQL. This closes same-code replay races.
    user = _lock_user(db, principal.user.id)
    admin_session = _lock_session(db, principal.session.id)
    if user.mfa_enabled_at is None or not user.mfa_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA is not enrolled")

    now = datetime.now(timezone.utc)
    recovery_used = False
    valid = False
    try:
        secret = decrypt_totp_secret(user.mfa_secret_encrypted, _master_key(request))
    except MfaSecretError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MFA service is unavailable") from exc

    counter = verify_totp(secret, payload.code, last_counter=user.mfa_last_counter, now=now)
    if counter is not None:
        user.mfa_last_counter = counter
        valid = True
    else:
        try:
            digest = recovery_code_digest(payload.code)
        except ValueError:
            digest = None
        if digest:
            recovery = db.scalar(
                select(MfaRecoveryCode)
                .where(
                    MfaRecoveryCode.user_id == user.id,
                    MfaRecoveryCode.code_hash == digest,
                    MfaRecoveryCode.used_at.is_(None),
                )
                .with_for_update()
            )
            if recovery is not None:
                recovery.used_at = now
                recovery_used = True
                valid = True

    if not valid:
        _record_failed_factor(db, request, user, admin_session, "auth.mfa.verify")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication code")

    user.failed_login_count = 0
    user.locked_until = None
    admin_session.mfa_verified_at = now
    record_audit(
        db,
        action="auth.mfa.verify",
        outcome="success",
        actor_user_id=user.id,
        target_type="session",
        target_id=admin_session.id,
        request_id=_request_id(request),
        metadata={"recovery_code_used": recovery_used},
    )
    db.commit()
    return MfaVerifyResponse(verified_at=now, recovery_code_used=recovery_used)


@router.post("/recovery-codes/regenerate", response_model=RecoveryCodesResponse)
def regenerate_recovery_codes(
    request: Request,
    principal: Annotated[Principal, Depends(require_sensitive_mutation())],
    db: Annotated[Session, Depends(get_db)],
) -> RecoveryCodesResponse:
    user = _lock_user(db, principal.user.id)
    admin_session = _lock_session(db, principal.session.id)
    _require_locked_step_up(admin_session)
    if admin_session.mfa_verified_at is None or user.mfa_enabled_at is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="multi-factor authentication required")
    codes = _replace_recovery_codes(db, user.id)
    record_audit(
        db,
        action="auth.mfa.recovery_regenerate",
        outcome="success",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        request_id=_request_id(request),
        metadata={"recovery_code_count": len(codes)},
    )
    db.commit()
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/disable", status_code=204)
def disable_mfa(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(require_sensitive_mutation())],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    settings = request.app.state.settings
    user = _lock_user(db, principal.user.id)
    admin_session = _lock_session(db, principal.session.id)
    _require_locked_step_up(admin_session)
    if admin_session.mfa_verified_at is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="multi-factor authentication required")
    if settings.require_mfa_for_privileged and user.role in PRIVILEGED_MFA_ROLES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA is mandatory for this role")
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    user.mfa_secret_encrypted = None
    user.mfa_pending_secret_encrypted = None
    user.mfa_pending_expires_at = None
    user.mfa_enabled_at = None
    user.mfa_last_counter = -1
    admin_session.mfa_verified_at = None
    record_audit(
        db,
        action="auth.mfa.disable",
        outcome="success",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        request_id=_request_id(request),
    )
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/cancel-session", status_code=204)
def cancel_pending_session(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(require_base_csrf)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    admin_session = _lock_session(db, principal.session.id)
    now = datetime.now(timezone.utc)
    admin_session.revoked_at = now
    record_audit(
        db,
        action="auth.mfa.cancel_session",
        outcome="success",
        actor_user_id=principal.user.id,
        target_type="session",
        target_id=admin_session.id,
        request_id=_request_id(request),
    )
    db.commit()
    settings = request.app.state.settings
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.secure_cookies, samesite="strict")
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.secure_cookies, samesite="strict")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
