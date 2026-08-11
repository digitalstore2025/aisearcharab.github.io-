from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .auth import Principal, require_permissions
from .database import get_db
from .models import ContentItem
from .schemas import ContentDetail

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/content/{content_id}", response_model=ContentDetail)
def admin_content_detail(
    content_id: str,
    principal: Annotated[Principal, Depends(require_permissions("content:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> ContentDetail:
    statement = (
        select(ContentItem)
        .where(ContentItem.id == content_id)
        .options(selectinload(ContentItem.sources), selectinload(ContentItem.claims))
    )
    item = db.scalar(statement)
    if item is None:
        raise HTTPException(status_code=404, detail="content not found")
    if item.status != "published" and "content:read_drafts" not in principal.permissions:
        raise HTTPException(status_code=403, detail="insufficient permissions for non-public content")
    return ContentDetail.model_validate(item)
