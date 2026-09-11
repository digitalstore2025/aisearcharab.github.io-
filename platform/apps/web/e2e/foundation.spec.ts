import { expect, test } from '@playwright/test';

test('renders hardened RTL workspace navigation and active state', async ({ page }) => {
  const response = await page.goto('/');
  expect(response?.ok()).toBeTruthy();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { name: 'AISearchArab' })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/);
  await expect(page.locator('img').first()).toHaveAttribute('src', '/brand-mark.svg');

  const headers = response?.headers() ?? {};
  expect(headers['content-security-policy']).toContain("object-src 'none'");
  expect(headers['content-security-policy']).toContain("frame-ancestors 'none'");
  expect(headers['content-security-policy']).toContain("form-action 'self'");
  expect(headers['referrer-policy']).toBe('no-referrer');
  expect(headers['x-content-type-options']).toBe('nosniff');
  expect(headers['x-robots-tag']).toContain('noindex');

  await page.getByRole('link', { name: 'فتح مساحة العمل' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('link', { name: 'لوحة العمل' })).toHaveAttribute('aria-current', 'page');
});

test('search uses URL state and fails closed without an explicitly enabled upstream API', async ({ page }) => {
  await page.goto('/search');
  await page.getByLabel('الاستعلام').fill('غزة');
  await page.getByRole('button', { name: 'بحث' }).click();

  await expect(page).toHaveURL(/\/search\?q=%D8%BA%D8%B2%D8%A9/);
  await expect(page.getByText('خدمة البحث غير متاحة في هذه البيئة حالياً. لم يتم إرسال الاستعلام إلى أي مزود بديل.')).toBeVisible();
});

test('foundation remains noindex before canonical launch', async ({ request }) => {
  const response = await request.get('/robots.txt');
  expect(response.ok()).toBeTruthy();
  expect(await response.text()).toContain('Disallow: /');
  expect(response.headers()['x-robots-tag']).toContain('noindex');
});
