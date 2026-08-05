from __future__ import annotations

import re
import unicodedata

ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#/_-]*|[\u0600-\u06FF]+")
WHITESPACE = re.compile(r"\s+")

PROTECTED_ENTITIES = (
    "gpt-5",
    "gemini 2.5",
    "claude",
    "llama",
    "openai api",
    "github",
    "python",
    "javascript",
    "128k",
    "aisearcharab.com",
)

_TRANSLATION = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ـ": "",
    }
)


def normalize_text(value: str) -> str:
    """Normalize Arabic and Latin text without destructive stemming."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = ARABIC_DIACRITICS.sub("", normalized)
    normalized = normalized.translate(_TRANSLATION)
    normalized = WHITESPACE.sub(" ", normalized).strip()
    return normalized


def tokenize(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_PATTERN.findall(normalize_text(value)))


def protected_entities_in(value: str) -> tuple[str, ...]:
    normalized = normalize_text(value)
    return tuple(entity for entity in PROTECTED_ENTITIES if entity in normalized)
