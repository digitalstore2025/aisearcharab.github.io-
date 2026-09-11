import { afterEach, describe, expect, it, vi } from 'vitest';
import { publicContentUrl, searchContent, SearchUnavailableError } from '@/server/api/search';

const ORIGINAL_ENV = { ...process.env };

function responseFixture(query = 'غزة') {
  return {
    query,
    normalized_query: query,
    algorithm_version: 'lexical-v1',
    retrieval_mode: 'retrieval-only',
    total: 1,
    limit: 10,
    offset: 0,
    took_ms: 1.2,
    results: [{ slug: 'gaza', url: '/reports/gaza/', title: 'غزة', summary: 'ملخص موثوق', section: 'reports', language: 'ar', published_at: null, score: 10, matched_fields: ['title'], source_authority: 8 }],
  };
}

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('search security boundary', () => {
  it('fails closed and performs no fetch unless search is explicitly enabled', async () => {
    process.env.AISEARCH_API_BASE_URL = 'https://api.example.com';
    delete process.env.AISEARCH_SEARCH_ENABLED;
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await expect(searchContent('غزة', 0)).rejects.toBeInstanceOf(SearchUnavailableError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ['', 0],
    ['x', 0],
    ['x'.repeat(121), 0],
    ['غزة', -10],
    ['غزة', 1],
    ['غزة', 300],
    ['غزة', Number.NaN],
  ])('rejects invalid direct calls before any network request: %j / %j', async (query, offset) => {
    process.env.AISEARCH_SEARCH_ENABLED = 'true';
    process.env.AISEARCH_API_BASE_URL = 'https://api.example.com';
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await expect(searchContent(query, offset)).rejects.toBeInstanceOf(SearchUnavailableError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('uses a fixed-origin GET, refuses redirects, and accepts a bounded JSON response', async () => {
    process.env.AISEARCH_SEARCH_ENABLED = 'true';
    process.env.AISEARCH_API_BASE_URL = 'https://api.example.com';
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(responseFixture()), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(searchContent('غزة', 0)).resolves.toMatchObject({ total: 1, limit: 10, offset: 0 });
    const [url, options] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(url.origin).toBe('https://api.example.com');
    expect(url.pathname).toBe('/v1/search');
    expect(url.searchParams.get('q')).toBe('غزة');
    expect(options.redirect).toBe('error');
    expect(options.cache).toBe('no-store');
  });

  it('rejects an oversized declared upstream response before reading it', async () => {
    process.env.AISEARCH_SEARCH_ENABLED = 'true';
    process.env.AISEARCH_API_BASE_URL = 'https://api.example.com';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'content-type': 'application/json', 'content-length': '300000' },
    })));

    await expect(searchContent('غزة', 0)).rejects.toBeInstanceOf(SearchUnavailableError);
  });

  it('cancels an oversized streamed upstream response even without content-length', async () => {
    process.env.AISEARCH_SEARCH_ENABLED = 'true';
    process.env.AISEARCH_API_BASE_URL = 'https://api.example.com';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('x'.repeat(300_000), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })));

    await expect(searchContent('غزة', 0)).rejects.toBeInstanceOf(SearchUnavailableError);
  });

  it('cannot turn a backslash-prefixed local path into a cross-origin URL', () => {
    process.env.AISEARCH_PUBLIC_SITE_ORIGIN = 'https://aisearcharab.com';
    expect(() => publicContentUrl('/\\evil.example')).toThrow();
    expect(publicContentUrl('/reports/gaza/')).toBe('https://aisearcharab.com/reports/gaza/');
  });
});
