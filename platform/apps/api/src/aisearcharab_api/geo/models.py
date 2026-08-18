from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organizations_slug"),
        Index("ix_organizations_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan", passive_deletes=True
    )
    projects: Mapped[list[GeoProject]] = relationship(
        back_populates="organization", cascade="all, delete-orphan", passive_deletes=True
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner','admin','analyst','viewer')", name="ck_org_membership_role"),
        UniqueConstraint("organization_id", "user_id", name="uq_org_membership_org_user"),
        Index("ix_org_membership_user_org", "user_id", "organization_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="memberships")


class GeoProject(Base):
    __tablename__ = "geo_projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_geo_projects_org_slug"),
        CheckConstraint("status IN ('active','paused','archived')", name="ck_geo_project_status"),
        Index("ix_geo_projects_org_status", "organization_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="projects")
