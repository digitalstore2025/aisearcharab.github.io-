from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from .audit import record_audit
from .auth import Principal, require_mutation, require_permissions, require_sensitive_mutation, require_step_up
from .database import get_db
from .models import AdminSession, AuditEvent, Claim, ContentItem, Source, User
from .routes_auth import user_public
from .schemas import (
    AuditEventPublic, ClaimCreate, ClaimReviewRequest, ClaimSummary,
    ContentAdminSummary, ContentCreate, ContentDetail, ContentTransitionRequest,
    ContentUpdate, SourceCreate, UserCreate, UserPublic, UserUpdate,
)
from .security import PasswordPolicyError, hash_password, normalize_email

router = APIRouter(prefix="/admin", tags=["admin"])
_EDITABLE_STATES = {"draft", "reviewed"}
_PUBLISHABLE_CLAIM_STATES = {"reviewed", "published"}


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _summary(item: ContentItem) -> ContentAdminSummary:
    return ContentAdminSummary.model_validate({
        "id": item.id, "slug": item.slug, "url_path": item.url_path,
        "title": item.title, "section": item.section, "language": item.language,
        "status": item.status, "is_indexed": item.is_indexed,
        "source_authority": item.source_authority, "published_at": item.published_at,
        "updated_at": item.updated_at, "source_count": len(item.sources),
        "claim_count": len(item.claims),
    })


def _content(db: Session, content_id: str, *, lock: bool = False) -> ContentItem:
    stmt = select(ContentItem).where(ContentItem.id == content_id).options(
        selectinload(ContentItem.sources), selectinload(ContentItem.claims)
    )
    if lock:
        stmt = stmt.with_for_update()
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(status_code=404, detail="content not found")
    return item


def _editable(item: ContentItem) -> None:
    if item.status not in _EDITABLE_STATES:
        raise HTTPException(status_code=409, detail="published or archived content must return to draft before editing")


def _demote(item: ContentItem) -> bool:
    if item.status != "reviewed":
        return False
    item.status = "draft"
    item.is_indexed = False
    item.reviewed_by_user_id = None
    item.published_by_user_id = None
    return True


def _sod(request: Request, actor: str, *prior: str | None) -> None:
    if not request.app.state.settings.enforce_separation_of_duties:
        return
    if any(value is None for value in prior):
        raise HTTPException(status_code=409, detail="editorial provenance is incomplete")
    if actor in {value for value in prior if value is not None}:
        raise HTTPException(status_code=409, detail="separation of duties requires a different user")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="concurrent modification detected; reload and retry") from exc


def _revoke_sessions(db: Session, user_id: str) -> None:
    db.execute(update(AdminSession).where(
        AdminSession.user_id == user_id, AdminSession.revoked_at.is_(None)
    ).values(revoked_at=datetime.now(timezone.utc)))


@router.get("/users", response_model=list[UserPublic])
def list_users(
    principal: Annotated[Principal, Depends(require_permissions("users:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserPublic]:
    return [user_public(user) for user in db.scalars(select(User).order_by(User.created_at.asc())).all()]


@router.post("/users", response_model=UserPublic, status_code=201)
def create_user(
    payload: UserCreate, request: Request,
    principal: Annotated[Principal, Depends(require_sensitive_mutation("users:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserPublic:
    try:
        email = normalize_email(payload.email)
        encoded = hash_password(payload.password, minimum_length=request.app.state.settings.password_min_length)
    except (ValueError, PasswordPolicyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = User(email=email, display_name=payload.display_name.strip(), role=payload.role, password_hash=encoded)
    db.add(user)
    try:
        db.flush()
        record_audit(db, action="user.create", outcome="success", actor_user_id=principal.user.id,
                     target_type="user", target_id=user.id, request_id=_rid(request), metadata={"role": payload.role})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="email already exists") from exc
    db.refresh(user)
    return user_public(user)


@router.patch("/users/{user_id}", response_model=UserPublic)
def update_user(
    user_id: str, payload: UserUpdate, request: Request,
    principal: Annotated[Principal, Depends(require_sensitive_mutation("users:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserPublic:
    if not payload.model_dump(exclude_unset=True):
        raise HTTPException(status_code=400, detail="no changes supplied")
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if user.id == principal.user.id and (payload.is_active is False or (payload.role is not None and payload.role != user.role)):
        raise HTTPException(status_code=400, detail="cannot disable or change your own role")
    owner_ids = list(db.scalars(select(User.id).where(User.role == "owner", User.is_active.is_(True)).with_for_update()).all())
    removing_last = user.role == "owner" and user.is_active and len(owner_ids) <= 1 and (
        payload.is_active is False or (payload.role is not None and payload.role != "owner")
    )
    if removing_last:
        raise HTTPException(status_code=400, detail="cannot remove the last active owner")
    security_change = False
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.role is not None and payload.role != user.role:
        user.role = payload.role; security_change = True
    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active; security_change = True
    if payload.password is not None:
        try:
            user.password_hash = hash_password(payload.password, minimum_length=request.app.state.settings.password_min_length)
        except PasswordPolicyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        user.password_changed_at = datetime.now(timezone.utc); security_change = True
    if security_change:
        _revoke_sessions(db, user.id)
    record_audit(db, action="user.update", outcome="success", actor_user_id=principal.user.id,
                 target_type="user", target_id=user.id, request_id=_rid(request),
                 metadata={"security_change": security_change, "role": user.role, "active": user.is_active})
    db.commit(); db.refresh(user)
    return user_public(user)


@router.get("/content", response_model=list[ContentAdminSummary])
def list_content(
    principal: Annotated[Principal, Depends(require_permissions("content:read"))],
    db: Annotated[Session, Depends(get_db)],
    content_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ContentAdminSummary]:
    stmt = select(ContentItem).options(selectinload(ContentItem.sources), selectinload(ContentItem.claims))
    draft_access = "content:read_drafts" in principal.permissions
    if content_status is not None:
        if content_status not in {"draft", "reviewed", "published", "archived"}:
            raise HTTPException(status_code=422, detail="invalid content status")
        if content_status != "published" and not draft_access:
            raise HTTPException(status_code=403, detail="insufficient permissions for non-public content")
        stmt = stmt.where(ContentItem.status == content_status)
    elif not draft_access:
        stmt = stmt.where(ContentItem.status == "published")
    return [_summary(item) for item in db.scalars(stmt.order_by(ContentItem.updated_at.desc()).limit(limit)).all()]


@router.post("/content", response_model=ContentDetail, status_code=201)
def create_content(
    payload: ContentCreate, request: Request,
    principal: Annotated[Principal, Depends(require_mutation("content:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> ContentDetail:
    item = ContentItem(
        slug=payload.slug, url_path=payload.url_path, title=payload.title.strip(),
        summary=payload.summary.strip(), body=payload.body.strip(), section=payload.section,
        language=payload.language, status="draft", is_indexed=False,
        source_authority=payload.source_authority, created_by_user_id=principal.user.id,
        last_modified_by_user_id=principal.user.id,
    )
    db.add(item)
    try:
        db.flush()
        record_audit(db, action="content.create", outcome="success", actor_user_id=principal.user.id,
                     target_type="content", target_id=item.id, request_id=_rid(request),
                     metadata={"slug": item.slug, "status": item.status})
        db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="slug already exists") from exc
    return ContentDetail.model_validate(_content(db, item.id))


@router.patch("/content/{content_id}", response_model=ContentDetail)
def update_content(
    content_id: str, payload: ContentUpdate, request: Request,
    principal: Annotated[Principal, Depends(require_mutation("content:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> ContentDetail:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="no changes supplied")
    item = _content(db, content_id, lock=True); _editable(item); previous = item.status
    for field, value in changes.items():
        setattr(item, field, value.strip() if isinstance(value, str) else value)
    item.last_modified_by_user_id = principal.user.id
    invalidated = _demote(item)
    record_audit(db, action="content.update", outcome="success", actor_user_id=principal.user.id,
                 target_type="content", target_id=item.id, request_id=_rid(request),
                 metadata={"from_status": previous, "to_status": item.status, "review_invalidated": invalidated})
    _commit(db)
    return ContentDetail.model_validate(_content(db, item.id))


@router.post("/content/{content_id}/transition", response_model=ContentDetail)
def transition_content(
    content_id: str, payload: ContentTransitionRequest, request: Request,
    principal: Annotated[Principal, Depends(require_mutation("content:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> ContentDetail:
    item = _content(db, content_id, lock=True)
    allowed = {"draft": {"reviewed"}, "reviewed": {"draft", "published"},
               "published": {"archived"}, "archived": {"draft"}}
    if payload.status not in allowed[item.status]:
        raise HTTPException(status_code=409, detail="invalid workflow transition")
    required = {"draft": "content:write", "reviewed": "content:review",
                "published": "content:publish", "archived": "content:publish"}[payload.status]
    if required not in principal.permissions:
        raise HTTPException(status_code=403, detail="insufficient permissions for transition")
    if payload.status in {"published", "archived"}:
        require_step_up(principal)
    if payload.status == "reviewed":
        if not item.sources:
            raise HTTPException(status_code=409, detail="at least one source is required before review approval")
        _sod(request, principal.user.id, item.created_by_user_id, item.last_modified_by_user_id)
        item.reviewed_by_user_id = principal.user.id; item.published_by_user_id = None
    if payload.status == "published":
        if not item.sources:
            raise HTTPException(status_code=409, detail="at least one source is required before publishing")
        claims = list(db.scalars(select(Claim).where(Claim.content_id == content_id).with_for_update()).all())
        if any(claim.review_status not in _PUBLISHABLE_CLAIM_STATES for claim in claims):
            raise HTTPException(status_code=409, detail="all claims must be approved before publishing")
        _sod(request, principal.user.id, item.created_by_user_id, item.last_modified_by_user_id, item.reviewed_by_user_id)
        item.published_by_user_id = principal.user.id
        item.published_at = item.published_at or datetime.now(timezone.utc); item.is_indexed = True
    elif payload.status in {"draft", "reviewed", "archived"}:
        item.is_indexed = False
    if payload.status == "draft":
        item.reviewed_by_user_id = None; item.published_by_user_id = None
    previous = item.status; item.status = payload.status
    record_audit(db, action="content.transition", outcome="success", actor_user_id=principal.user.id,
                 target_type="content", target_id=item.id, request_id=_rid(request),
                 metadata={"from": previous, "to": payload.status, "revision": item.revision})
    _commit(db)
    return ContentDetail.model_validate(_content(db, item.id))


@router.post("/content/{content_id}/sources", response_model=ContentDetail, status_code=201)
def add_source(
    content_id: str, payload: SourceCreate, request: Request,
    principal: Annotated[Principal, Depends(require_mutation("sources:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> ContentDetail:
    item = _content(db, content_id, lock=True); _editable(item)
    source = db.scalar(select(Source).where(Source.source_key == payload.source_key)); source_url = str(payload.url)
    if source is None:
        source = Source(source_key=payload.source_key, title=payload.title.strip(), publisher=payload.publisher.strip(),
                        url=source_url, archive_url=str(payload.archive_url) if payload.archive_url else None,
                        source_type=payload.source_type, language=payload.language, reliability=payload.reliability)
    elif source.url != source_url or source.title != payload.title.strip() or source.publisher != payload.publisher.strip():
        raise HTTPException(status_code=409, detail="source key already represents different source metadata")
    if source in item.sources:
        raise HTTPException(status_code=409, detail="source is already attached")
    item.sources.append(source)
    item.last_modified_by_user_id = principal.user.id
    previous = item.status; invalidated = _demote(item)
    record_audit(db, action="content.source.attach", outcome="success", actor_user_id=principal.user.id,
                 target_type="content", target_id=item.id, request_id=_rid(request),
                 metadata={"source_key": payload.source_key, "reliability": payload.reliability,
                           "from_status": previous, "review_invalidated": invalidated})
    try:
        _commit(db)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="source key conflict") from exc
    return ContentDetail.model_validate(_content(db, item.id))


@router.post("/content/{content_id}/claims", response_model=ContentDetail, status_code=201)
def add_claim(
    content_id: str, payload: ClaimCreate, request: Request,
    principal: Annotated[Principal, Depends(require_mutation("claims:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> ContentDetail:
    item = _content(db, content_id, lock=True); _editable(item)
    claim = Claim(claim_key=payload.claim_key, text=payload.text.strip(), claim_type=payload.claim_type,
                  confidence=payload.confidence, review_status="draft", created_by_user_id=principal.user.id)
    item.claims.append(claim)
    item.last_modified_by_user_id = principal.user.id
    previous = item.status; invalidated = _demote(item)
    try:
        db.flush()
        record_audit(db, action="content.claim.create", outcome="success", actor_user_id=principal.user.id,
                     target_type="claim", target_id=claim.id, request_id=_rid(request),
                     metadata={"content_id": item.id, "claim_key": payload.claim_key,
                               "claim_type": payload.claim_type, "from_status": previous,
                               "review_invalidated": invalidated})
        _commit(db)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="claim key already exists") from exc
    return ContentDetail.model_validate(_content(db, item.id))


@router.patch("/claims/{claim_id}", response_model=ClaimSummary)
def review_claim(
    claim_id: str, payload: ClaimReviewRequest, request: Request,
    principal: Annotated[Principal, Depends(require_mutation("claims:review"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClaimSummary:
    if payload.review_status == "published":
        require_step_up(principal)
    content_id = db.scalar(select(Claim.content_id).where(Claim.id == claim_id))
    if content_id is None:
        raise HTTPException(status_code=404, detail="claim not found")
    item = _content(db, content_id, lock=True)
    claim = db.scalar(select(Claim).where(Claim.id == claim_id, Claim.content_id == content_id).with_for_update())
    if claim is None:
        raise HTTPException(status_code=404, detail="claim not found")
    if item.status not in _EDITABLE_STATES:
        raise HTTPException(status_code=409, detail="claims on published or archived content cannot be changed")
    _sod(request, principal.user.id, claim.created_by_user_id)
    invalidated = _demote(item)
    claim.review_status = payload.review_status; claim.confidence = payload.confidence
    claim.reviewed_by_user_id = principal.user.id
    claim.verified_at = datetime.now(timezone.utc) if payload.review_status in _PUBLISHABLE_CLAIM_STATES else None
    record_audit(db, action="claim.review", outcome="success", actor_user_id=principal.user.id,
                 target_type="claim", target_id=claim.id, request_id=_rid(request),
                 metadata={"content_id": claim.content_id, "review_status": payload.review_status,
                           "confidence": payload.confidence, "content_review_invalidated": invalidated})
    _commit(db); db.refresh(claim)
    return ClaimSummary.model_validate(claim)


@router.get("/audit", response_model=list[AuditEventPublic])
def list_audit_events(
    principal: Annotated[Principal, Depends(require_permissions("audit:read"))],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=200),
) -> list[AuditEventPublic]:
    events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all())
    output: list[AuditEventPublic] = []
    for event in events:
        try:
            metadata = json.loads(event.metadata_json)
        except json.JSONDecodeError:
            metadata = {}
        output.append(AuditEventPublic(id=event.id, actor_user_id=event.actor_user_id, action=event.action,
                                       outcome=event.outcome, target_type=event.target_type, target_id=event.target_id,
                                       request_id=event.request_id, metadata=metadata if isinstance(metadata, dict) else {},
                                       created_at=event.created_at))
    return output
