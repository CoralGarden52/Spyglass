import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

test('real persisted report, source readback, repair versions and refresh', async ({ page }) => {
  const seed = JSON.parse(readFileSync('.artifacts/e2e-report-seed.json', 'utf8')) as {
    kind: string;
    email: string;
    project_id: string;
  };
  expect(seed.kind).toBe('isolated_synthetic_fixture');
  await page.setViewportSize({ width: 1586, height: 992 });
  await page.goto('/login');
  await page.getByRole('textbox', { name: '邮箱', exact: true }).fill(seed.email);
  await page.getByLabel('密码', { exact: true }).fill('Browser-test-passphrase-42');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page).toHaveURL('/');
  await page.goto(`/research/${seed.project_id}`);
  await page.getByRole('button', { name: /Controlled fixture report/ }).click();
  await expect(
    page.getByRole('heading', { name: 'Controlled fixture report', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.persisted-section')).toHaveCount(4);
  await page
    .locator('.report-claim')
    .first()
    .getByRole('button', { name: '证据 1', exact: true })
    .click();
  await expect(page.getByRole('dialog', { name: '证据来源' })).toContainText(
    'CONTROLLED SYNTHETIC FIXTURE',
  );
  await expect(page.getByRole('dialog', { name: '证据来源' })).toContainText('公开检索摘要');
  await expect(page.getByRole('dialog')).toContainText('86.0 / 100');
  await expect(page.getByRole('dialog')).toContainText('发布时间');
  await page.screenshot({ path: '.artifacts/screenshots/deepseek-source-metadata.png' });
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByText('质检与返工记录（2 次）', { exact: true }).click();
  await expect(page.getByText('第 1 次审查 · 定向返工', { exact: true })).toBeVisible();
  await expect(page.getByText('第 2 次审查 · 通过', { exact: true })).toBeVisible();
  await page.screenshot({ path: '.artifacts/screenshots/slice-3-report.png', fullPage: true });
  await page.reload();
  await page.getByRole('button', { name: /Controlled fixture report/ }).click();
  await expect(page.locator('.persisted-section')).toHaveCount(4);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
