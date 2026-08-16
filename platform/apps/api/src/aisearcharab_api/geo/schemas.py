from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _slug(value: str) -> str:
    normalized = value.strip().lower()
    if not _SLUG.fullmatch(normalized):
        raise ValueError("slug must contain lowercase letters, digits, and single hyphens only")
    return normalized


def _domain(value: str) -> str:
    normalized = value.strip().rstrip(".").lower()
    if not normalized or "/" in normalized or ":" in normalized or "@" in normalized:
        raise ValueError("domain must be a bare hostname without scheme, path, port, or credentials")
    try:
        ascii_domain = normalized.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("invalid domain") from exc
    if len(ascii_domain) > 253 or "." not in ascii_domain:
        raise ValueError("domain must be a valid registrable-style hostname")
    labels = ascii_domain.split(".")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        raise ValueError("invalid domain labels")
    if any(not re.fullmatch(r"[a-z0-9-]+", label) for label in labels):
        raise ValueError("invalid domain labels")
    return ascii_domain


class OrganizationCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)

    _normalize_slug = field_validator("slug")(_slug)


class OrganizationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    created_at: datetime


class GeoProjectCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    domain: str = Field(min_length=3, max_length=253)

    _normalize_slug = field_validator("slug")(_slug)
    _normalize_domain = field_validator("domain")(_domain)


class GeoProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    slug: str
    name: str
    domain: str
    status: str
    created_at: datetime
    updated_at: datetime


class MembershipPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: str
    user_id: str
    role: str
