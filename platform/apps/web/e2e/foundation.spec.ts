import { expect, test } from '@playwright/test';

test('renders RTL workspace navigation and active state', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { name: 'AI Search Arab' })).toBeVisible();

  await page.getByRole('link', { name: 'فتح مساحة العمل' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('link', { name: 'لوحة العمل' })).toHaveAttribute('aria-current', 'page');
});

test('search uses URL state and fails closed without an upstream API', async ({ page }) => {
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
});
