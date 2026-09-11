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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  if (typeof value !== 'string') throw new Error('Invalid search API contract');
  return value;
}

function readNumber(record: Record<string, unknown>, key: string): number {
  const value = record[key];
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('Invalid search API contract');
  return value;
}

function parseResult(value: unknown): SearchResult {
  if (!isRecord(value)) throw new Error('Invalid search API contract');
  const publishedAt = value.published_at;
  const matchedFields = value.matched_fields;
  if (publishedAt !== null && typeof publishedAt !== 'string') throw new Error('Invalid search API contract');
  if (!Array.isArray(matchedFields) || matchedFields.some((item) => typeof item !== 'string')) {
    throw new Error('Invalid search API contract');
  }
  return {
    slug: readString(value, 'slug'),
    url: readString(value, 'url'),
    title: readString(value, 'title'),
    summary: readString(value, 'summary'),
    section: readString(value, 'section'),
    language: readString(value, 'language'),
    published_at: publishedAt,
    score: readNumber(value, 'score'),
    matched_fields: matchedFields,
    source_authority: readNumber(value, 'source_authority'),
  };
}

export function parseSearchResponse(value: unknown): SearchResponse {
  if (!isRecord(value) || !Array.isArray(value.results)) throw new Error('Invalid search API contract');
  return {
    query: readString(value, 'query'),
    normalized_query: readString(value, 'normalized_query'),
    algorithm_version: readString(value, 'algorithm_version'),
    retrieval_mode: readString(value, 'retrieval_mode'),
    total: readNumber(value, 'total'),
    limit: readNumber(value, 'limit'),
    offset: readNumber(value, 'offset'),
    took_ms: readNumber(value, 'took_ms'),
    results: value.results.map(parseResult),
  };
}
