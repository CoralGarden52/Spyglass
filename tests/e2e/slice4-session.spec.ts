import { expect, test } from '@playwright/test';

async function register(page: import('@playwright/test').Page) {
  await page.goto('/register');
  await page.getByRole('textbox', { name: '姓名', exact: true }).fill('隔离会话验收');
  await page
    .getByRole('textbox', { name: '邮箱', exact: true })
    .fill(`slice4-${crypto.randomUUID()}@example.com`);
  await page.getByLabel('密码', { exact: true }).fill('Browser-test-passphrase-42');
  await page.getByRole('button', { name: '注册并进入工作台', exact: true }).click();
  await expect(page).toHaveURL('/');
}

test('public API research submission persists messages, events and report through refresh', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1586, height: 992 });
  await register(page);
  await page
    .getByRole('textbox', { name: '研究目标', exact: true })
    .fill('Controlled fixture: compare Alpha with public evidence');
  await expect(page.getByRole('button', { name: '开始分析', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '开始分析', exact: true }).click();
  await expect(page).toHaveURL(/\/threads\/[\w-]+$/);
  await expect(page.locator('.session-report .persisted-section')).toHaveCount(4, {
    timeout: 30000,
  });
  await expect(page.locator('.message-user')).toContainText('Controlled fixture: compare Alpha');
  await expect(page.locator('.message-assistant')).toHaveCount(1);
  await expect(page.locator('.run-status')).toContainText('已完成');
  await page.screenshot({
    path: '.artifacts/screenshots/slice4-session-desktop.png',
    fullPage: true,
  });
  const eventCount = await page.locator('.run-event').count();
  expect(eventCount).toBeGreaterThan(0);
  await page.reload();
  await expect(page.locator('.session-report .persisted-section')).toHaveCount(4);
  await expect(page.locator('.message-user')).toHaveCount(1);
  await expect(page.locator('.message-assistant')).toHaveCount(1);
  await expect(page.locator('.run-event')).toHaveCount(eventCount);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('tab', { name: '报告', exact: true }).click();
  await expect(page.locator('.session-report')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({
    path: '.artifacts/screenshots/slice4-session-mobile.png',
    fullPage: true,
  });
  await page.getByRole('tab', { name: '对话', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '追加研究需求' })).toBeVisible();
});

test('cancel requires confirmation and keeps the durable terminal state', async ({ page }) => {
  await register(page);
  await page
    .getByRole('textbox', { name: '研究目标', exact: true })
    .fill('Controlled fixture slow: compare Alpha');
  await page.getByRole('button', { name: '开始分析', exact: true }).click();
  await expect(page).toHaveURL(/\/threads\/[\w-]+$/);
  await page.getByRole('button', { name: '取消运行', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '确认取消运行' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: '继续研究', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole('button', { name: '取消运行', exact: true }).click();
  await page.getByRole('button', { name: '确认取消', exact: true }).click();
  await expect(page.locator('.run-status')).toContainText('已取消');
  await page.reload();
  await expect(page.locator('.run-status')).toContainText('已取消');
  await expect(page.getByRole('textbox', { name: '追加研究需求' })).toBeEnabled();
});
