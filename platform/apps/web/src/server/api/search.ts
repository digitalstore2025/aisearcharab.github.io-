import { parseSearchResponse, type SearchResponse } from '@/lib/contracts/search';
import { SEARCH_PAGE_SIZE } from '@/lib/search-request';
import { getApiBaseUrl, getPublicSiteOrigin } from './config';

const SEARCH_TIMEOUT_MS = 4500;

export class SearchUnavailableError extends Error {
  constructor() {
    super('Search service unavailable');
    this.name = 'SearchUnavailableError';
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
      signal: AbortSignal.timeout(SEARCH_TIMEOUT_MS),
    });
    if (!response.ok) throw new SearchUnavailableError();
    return parseSearchResponse(await response.json());
  } catch (error) {
    if (error instanceof SearchUnavailableError) throw error;
    throw new SearchUnavailableError();
  }
}

export function publicContentUrl(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//')) throw new Error('Invalid public content path');
  return new URL(path, getPublicSiteOrigin()).toString();
}
