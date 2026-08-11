from __future__ import annotations

from dataclasses import dataclass

PERMISSIONS = frozenset(
    {
        "content:read",
        "content:read_drafts",
        "content:write",
        "content:review",
        "content:publish",
        "sources:write",
        "claims:write",
        "claims:review",
        "users:read",
        "users:manage",
        "audit:read",
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": PERMISSIONS,
    "admin": frozenset(PERMISSIONS - {"users:manage"}),
    "editor": frozenset({"content:read", "content:read_drafts", "content:write", "sources:write", "claims:write"}),
    "reviewer": frozenset({"content:read", "content:read_drafts", "content:review", "claims:review"}),
    "publisher": frozenset({"content:read", "content:read_drafts", "content:publish"}),
    "analyst": frozenset({"content:read", "audit:read"}),
}

ROLES = frozenset(ROLE_PERMISSIONS)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    role: str
    missing_permissions: tuple[str, ...]


def permissions_for_role(role: str) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def authorize(role: str, required: tuple[str, ...]) -> AuthorizationDecision:
    granted = permissions_for_role(role)
    missing = tuple(permission for permission in required if permission not in granted)
    return AuthorizationDecision(allowed=not missing, role=role, missing_permissions=missing)
