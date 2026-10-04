export type SearchResult = Readonly<{
  slug: string;
  url: string;
  title: string;
  summary: string;
  section: string;
  language: string;
  published_at: string | null;
  score: number;
  matched_fields: readonly string[];
  source_authority: number;
}>;

export type SearchResponse = Readonly<{
  query: string;
  normalized_query: string;
  algorithm_version: string;
  retrieval_mode: string;
  total: number;
  limit: number;
  offset: number;
  took_ms: number;
  results: readonly SearchResult[];
}>;

const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/;
const ENCODED_PATH_SEPARATOR = /%(?:2f|5c)/i;
const SLUG = /^[a-z0-9][a-z0-9-]*$/;

function invalid(): never {
  throw new Error('Invalid search API contract');
}

export function assertSafeLocalContentPath(value: string): string {
  if (
    !value.startsWith('/')
    || value.startsWith('//')
    || value.includes('\\')
    || value.includes('?')
    || value.includes('#')
    || value.includes('://')
    || CONTROL_CHARACTERS.test(value)
    || ENCODED_PATH_SEPARATOR.test(value)
  ) {
    invalid();
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readString(record: Record<string, unknown>, key: string, minLength: number, maxLength: number): string {
  const value = record[key];
  if (typeof value !== 'string' || value.length < minLength || value.length > maxLength) invalid();
  return value;
}

function readInteger(record: Record<string, unknown>, key: string, min: number, max: number): number {
  const value = record[key];
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid();
  return value;
}

function readFiniteNumber(record: Record<string, unknown>, key: string, min: number, max: number): number {
  const value = record[key];
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) invalid();
  return value;
}

function parseResult(value: unknown): SearchResult {
  if (!isRecord(value)) invalid();
  const publishedAt = value.published_at;
  const matchedFields = value.matched_fields;
  const slug = readString(value, 'slug', 1, 180);
  if (!SLUG.test(slug)) invalid();
  if (publishedAt !== null) {
    if (typeof publishedAt !== 'string' || publishedAt.length > 64 || Number.isNaN(Date.parse(publishedAt))) invalid();
  }
  if (
    !Array.isArray(matchedFields)
    || matchedFields.length > 16
    || matchedFields.some((item) => typeof item !== 'string' || item.length < 1 || item.length > 64)
  ) {
    invalid();
  }
  return {
    slug,
    url: assertSafeLocalContentPath(readString(value, 'url', 1, 500)),
    title: readString(value, 'title', 1, 300),
    summary: readString(value, 'summary', 1, 2000),
    section: readString(value, 'section', 1, 80),
    language: readString(value, 'language', 2, 12),
    published_at: publishedAt,
    score: readFiniteNumber(value, 'score', 0, Number.MAX_SAFE_INTEGER),
    matched_fields: matchedFields,
    source_authority: readFiniteNumber(value, 'source_authority', 0, 10),
  };
}

export function parseSearchResponse(value: unknown): SearchResponse {
  if (!isRecord(value) || !Array.isArray(value.results) || value.results.length > 20) invalid();
  return {
    query: readString(value, 'query', 2, 120),
    normalized_query: readString(value, 'normalized_query', 1, 240),
    algorithm_version: readString(value, 'algorithm_version', 1, 64),
    retrieval_mode: readString(value, 'retrieval_mode', 1, 64),
    total: readInteger(value, 'total', 0, Number.MAX_SAFE_INTEGER),
    limit: readInteger(value, 'limit', 1, 20),
    offset: readInteger(value, 'offset', 0, 10_000),
    took_ms: readFiniteNumber(value, 'took_ms', 0, Number.MAX_SAFE_INTEGER),
    results: value.results.map(parseResult),
  };
}
