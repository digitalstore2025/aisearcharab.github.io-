from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .arabic import normalize_text, protected_entities_in, tokenize
from .models import ContentItem


@dataclass(frozen=True, slots=True)
class RankedItem:
    item: ContentItem
    score: float
    matched_fields: tuple[str, ...]


def _freshness_bonus(published_at: datetime | None) -> float:
    if published_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    value = published_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age_days = max((now - value).days, 0)
    if age_days <= 30:
        return 8.0
    if age_days <= 180:
        return 4.0
    if age_days <= 365:
        return 2.0
    return 0.0


def _token_hit_count(query_tokens: tuple[str, ...], value: str) -> int:
    field_tokens = set(tokenize(value))
    return sum(1 for token in query_tokens if token in field_tokens)


def rank_item(query: str, item: ContentItem) -> RankedItem | None:
    normalized_query = normalize_text(query)
    query_tokens = tuple(dict.fromkeys(tokenize(query)))
    if not normalized_query or not query_tokens:
        return None

    title = normalize_text(item.title)
    summary = normalize_text(item.summary)
    body = normalize_text(item.body)
    section = normalize_text(item.section)

    score = 0.0
    matched: list[str] = []

    if normalized_query == title:
        score += 140.0
        matched.append("title-exact")
    elif len(query_tokens) > 1 and normalized_query in title:
        score += 90.0
        matched.append("title-phrase")

    title_hits = _token_hit_count(query_tokens, title)
    summary_hits = _token_hit_count(query_tokens, summary)
    body_hits = _token_hit_count(query_tokens, body)
    section_hits = _token_hit_count(query_tokens, section)

    if title_hits:
        score += title_hits * 22.0
        matched.append("title")
    if summary_hits:
        score += summary_hits * 9.0
        matched.append("summary")
    if body_hits:
        score += body_hits * 2.5
        matched.append("body")
    if section_hits:
        score += section_hits * 5.0
        matched.append("section")

    if len(query_tokens) > 1 and normalized_query in summary:
        score += 25.0
    if len(query_tokens) > 1 and normalized_query in body:
        score += 8.0

    total_distinct_hits = len(
        set(query_tokens)
        & (set(tokenize(title)) | set(tokenize(summary)) | set(tokenize(body)) | set(tokenize(section)))
    )
    if total_distinct_hits == len(query_tokens) and len(query_tokens) > 1:
        score += 12.0
        matched.append("all-query-terms")

    protected = protected_entities_in(query)
    for entity in protected:
        if entity in title:
            score += 60.0
            matched.append("protected-entity")
        elif entity in summary:
            score += 28.0
            matched.append("protected-entity")
        elif entity in body:
            score += 12.0
            matched.append("protected-entity")

    if not matched:
        return None

    score += max(min(item.source_authority, 10.0), 0.0) * 1.8
    score += _freshness_bonus(item.published_at)
    return RankedItem(item=item, score=round(score, 3), matched_fields=tuple(dict.fromkeys(matched)))


def _published_timestamp(value: datetime | None) -> float:
    if value is None:
        return float("-inf")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def rank_items(query: str, items: list[ContentItem]) -> list[RankedItem]:
    ranked = [result for item in items if (result := rank_item(query, item)) is not None]
    return sorted(
        ranked,
        key=lambda result: (-result.score, -_published_timestamp(result.item.published_at), result.item.slug),
    )
