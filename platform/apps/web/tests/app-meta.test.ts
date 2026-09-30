import { describe, expect, it } from 'vitest';
import { APP_META } from '../src/lib/app-meta';

describe('APP_META', () => {
  it('keeps a stable product identity', () => {
    expect(APP_META.name).toBe('AISearchArab');
    expect(APP_META.phase).toContain('Sprint 0');
  });
});
