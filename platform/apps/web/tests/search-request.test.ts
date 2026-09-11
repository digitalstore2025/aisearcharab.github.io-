import { describe, expect, it } from 'vitest';
import { parseSearchRequest } from '@/lib/search-request';

describe('search URL request parsing', () => {
  it('creates bounded offsets', () => expect(parseSearchRequest({ q: 'غزة', page: '3' })).toMatchObject({ status: 'ready', page: 3, offset: 20 }));
  it('rejects overlong queries', () => expect(parseSearchRequest({ q: 'x'.repeat(121) }).status).toBe('invalid'));
  it('rejects pages beyond the ranked candidate window', () => expect(parseSearchRequest({ q: 'بحث', page: '31' }).status).toBe('invalid'));
});
