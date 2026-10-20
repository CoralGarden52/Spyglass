import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page, baseURL }) => {
  const response = await page.request.post('/api/v1/auth/register', {
    headers: { Origin: new URL(baseURL!).origin },
    data: {
      email: `baseline-${crypto.randomUUID()}@example.com`,
      password: 'Browser-test-passphrase-42',
      display_name: '测试研究员',
    },
  });
  expect(response.status()).toBe(201);
});

test('desktop workbench reads real API and respects the reference structure', async ({ page }) => {
  await page.setViewportSize({ width: 1672, height: 941 });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('基础服务已就绪')).toBeVisible();
  await expect(page.getByText('PostgreSQL 已连接')).toBeVisible();
  await expect(page.getByText('Redis 已连接')).toBeVisible();
  await expect(page.getByRole('complementary')).not.toContainText('场景技能');
  await expect(page.getByRole('button', { name: '开始分析' })).toBeDisabled();
  await expect(page.getByText(/研究执行尚未开放/)).toBeVisible();
  await page.getByRole('button', { name: '竞品深度分析' }).click();
  await expect(page.getByRole('textbox', { name: '研究目标' })).toHaveValue(/Cursor/);
  await page.getByRole('button', { name: '深度调研', exact: true }).click();
  await expect(page.getByRole('button', { name: '深度调研', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(page.getByRole('button', { name: '标准调研', exact: true })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: '.artifacts/screenshots/slice-1-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('mobile navigation and keyboard input remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByText('基础服务已就绪')).toBeVisible();
  await page.getByRole('button', { name: '打开导航' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  await page.getByRole('button', { name: '关闭导航', exact: true }).click();
  await page.getByRole('link', { name: '新建调研' }).click();
  await expect(page.getByRole('textbox', { name: '研究目标' })).toBeFocused();
  await page.keyboard.type('Compare developer tools');
  await expect(page.getByRole('textbox', { name: '研究目标' })).toHaveValue(
    'Compare developer tools',
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: '.artifacts/screenshots/slice-1-mobile.png', fullPage: true });
});
