import { assertSafeLocalContentPath, parseSearchResponse, type SearchResponse } from '@/lib/contracts/search';
import { SEARCH_PAGE_SIZE } from '@/lib/search-request';
import { getApiBaseUrl, getPublicSiteOrigin } from './config';

const SEARCH_TIMEOUT_MS = 4500;
const MAX_SEARCH_RESPONSE_BYTES = 256 * 1024;

export class SearchUnavailableError extends Error {
  constructor() {
    super('Search service unavailable');
    this.name = 'SearchUnavailableError';
  }
}

async function readBoundedJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type')?.split(';', 1)[0]?.trim().toLowerCase();
  if (contentType !== 'application/json') throw new SearchUnavailableError();

  const contentLength = response.headers.get('content-length');
  if (contentLength) {
    const declaredBytes = Number(contentLength);
    if (!Number.isFinite(declaredBytes) || declaredBytes < 0 || declaredBytes > MAX_SEARCH_RESPONSE_BYTES) {
      throw new SearchUnavailableError();
    }
  }

  const body = await response.text();
  if (new TextEncoder().encode(body).byteLength > MAX_SEARCH_RESPONSE_BYTES) throw new SearchUnavailableError();

  try {
    return JSON.parse(body) as unknown;
  } catch {
    throw new SearchUnavailableError();
  }
}

export async function searchContent(query: string, offset: number): Promise<SearchResponse> {
  const apiBase = getApiBaseUrl();
  if (!apiBase) throw new SearchUnavailableError();

  const url = new URL('/v1/search', apiBase);
  url.searchParams.set('q', query);
  url.searchParams.set('limit', String(SEARCH_PAGE_SIZE));
  url.searchParams.set('offset', String(offset));

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: { accept: 'application/json' },
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(SEARCH_TIMEOUT_MS),
    });
    if (!response.ok) throw new SearchUnavailableError();
    const parsed = parseSearchResponse(await readBoundedJson(response));
    if (
      parsed.query !== query
      || parsed.limit !== SEARCH_PAGE_SIZE
      || parsed.offset !== offset
      || parsed.results.length > SEARCH_PAGE_SIZE
      || parsed.total < parsed.offset + parsed.results.length
    ) {
      throw new SearchUnavailableError();
    }
    return parsed;
  } catch (error) {
    if (error instanceof SearchUnavailableError) throw error;
    throw new SearchUnavailableError();
  }
}

export function publicContentUrl(path: string): string {
  const safePath = assertSafeLocalContentPath(path);
  const publicOrigin = getPublicSiteOrigin();
  const resolved = new URL(safePath, publicOrigin);
  if (resolved.origin !== publicOrigin) throw new Error('Invalid public content path');
  return resolved.toString();
}
