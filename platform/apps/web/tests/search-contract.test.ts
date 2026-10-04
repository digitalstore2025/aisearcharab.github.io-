import { describe, expect, it } from 'vitest';
import { assertSafeLocalContentPath, parseSearchResponse } from '@/lib/contracts/search';

const fixture = {
  query: 'حوكمة الذكاء الاصطناعي', normalized_query: 'حوكمه الذكاء الاصطناعي', algorithm_version: 'lexical-v1', retrieval_mode: 'retrieval-only', total: 1, limit: 10, offset: 0, took_ms: 4.2,
  results: [{ slug: 'governance', url: '/reports/governance/', title: 'حوكمة الذكاء الاصطناعي', summary: 'ملخص', section: 'reports', language: 'ar', published_at: null, score: 2.1, matched_fields: ['title'], source_authority: 0.9 }],
};

describe('search API contract', () => {
  it('parses the reviewed response shape', () => expect(parseSearchResponse(fixture).results[0]?.slug).toBe('governance'));
  it('rejects malformed result fields', () => expect(() => parseSearchResponse({ ...fixture, total: '1' })).toThrow('Invalid search API contract'));
  it.each(['/\\evil.example', '//evil.example', '/%5cevil.example', '/%2f%2fevil.example', '/report?next=x', '/report#fragment'])('rejects unsafe local paths: %s', (path) => {
    expect(() => assertSafeLocalContentPath(path)).toThrow('Invalid search API contract');
    expect(() => parseSearchResponse({ ...fixture, results: [{ ...fixture.results[0], url: path }] })).toThrow('Invalid search API contract');
  });
  it('rejects oversized result collections', () => {
    const results = Array.from({ length: 21 }, (_, index) => ({ ...fixture.results[0], slug: `item-${index}` }));
    expect(() => parseSearchResponse({ ...fixture, total: 21, results })).toThrow('Invalid search API contract');
  });
});
