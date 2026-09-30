import { describe, expect, it } from 'vitest';
import { NAV_ITEMS } from '@/lib/navigation';

describe('workspace navigation', () => {
  it('contains unique stable routes', () => {
    const hrefs = NAV_ITEMS.map((item) => item.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
    expect(hrefs).toEqual(['/dashboard', '/search', '/sources', '/research', '/projects']);
  });

  it('has accessible human labels', () => {
    for (const item of NAV_ITEMS) {
      expect(item.label.trim().length).toBeGreaterThan(1);
      expect(item.description.trim().length).toBeGreaterThan(8);
    }
  });
});
