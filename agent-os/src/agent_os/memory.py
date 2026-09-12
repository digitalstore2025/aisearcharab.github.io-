from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class MemoryItem:
    namespace: str
    key: str
    value: Any
    source: str
    verified: bool = False
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def usable_as_fact(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if self.expires_at and self.expires_at <= now:
            return False
        return self.verified


class MemoryStore:
    """In-memory reference implementation. Replace with durable storage in production."""

    ALLOWED_NAMESPACES = {"session", "project", "preferences", "verified_knowledge"}

    def __init__(self):
        self._items: dict[tuple[str, str], MemoryItem] = {}

    def put(self, item: MemoryItem) -> None:
        if item.namespace not in self.ALLOWED_NAMESPACES:
            raise ValueError(f"Unsupported namespace: {item.namespace}")
        self._items[(item.namespace, item.key)] = item

    def get(self, namespace: str, key: str, *, require_verified: bool = False) -> MemoryItem | None:
        item = self._items.get((namespace, key))
        if item is None:
            return None
        if require_verified and not item.usable_as_fact():
            return None
        return item
