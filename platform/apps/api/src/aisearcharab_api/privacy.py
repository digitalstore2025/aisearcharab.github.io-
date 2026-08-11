from __future__ import annotations

import hashlib
import hmac


def hash_query(normalized_query: str, key: str) -> str:
    """Create a keyed, non-reversible analytics identifier for a normalized query."""
    return hmac.new(key.encode("utf-8"), normalized_query.encode("utf-8"), hashlib.sha256).hexdigest()
