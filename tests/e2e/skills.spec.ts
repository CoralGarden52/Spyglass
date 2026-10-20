import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page, baseURL }) => {
  const response = await page.request.post('/api/v1/auth/register', {
    headers: { Origin: new URL(baseURL!).origin },
    data: {
      email: `skills-${crypto.randomUUID()}@example.com`,
      password: 'Browser-test-passphrase-42',
      display_name: '技能研究员',
    },
  });
  expect(response.status()).toBe(201);
});

test('real registry selection, core enforcement and automatic plan preview', async ({ page }) => {
  await page.setViewportSize({ width: 1672, height: 941 });
  await page.goto('/');
  await expect(page.getByRole('radio', { name: '通用分析', exact: true })).toBeChecked();
  await expect(page.getByRole('radio')).toHaveCount(6);
  await page.getByRole('radio', { name: 'AI 与大模型', exact: true }).check();
  await expect(page.getByRole('radio', { checked: true })).toHaveCount(1);
  await expect(page.getByRole('checkbox', { name: /必选/ })).toHaveCount(4);
  for (const item of await page.getByRole('checkbox', { name: /必选/ }).all()) {
    await expect(item).toBeDisabled();
    await expect(item).toBeChecked();
  }
  await page.getByRole('checkbox', { name: '市场格局分析', exact: true }).check();
  const preview = page.getByLabel('技能计划预览');
  await expect(preview).toContainText('6 项技能');
  await expect(preview).toContainText('v0.1.0');
  await page.getByRole('button', { name: '自动选择', exact: true }).click();
  await page.getByRole('button', { name: '深度调研', exact: true }).click();
  await expect(preview).toContainText('8 项技能');
  await expect(page.getByRole('checkbox', { name: '市场格局分析', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '开始分析', exact: true })).toBeDisabled();
  await page.screenshot({ path: '.artifacts/screenshots/slice-2-workbench.png', fullPage: true });
});

test('skill centre filters and persists tenant configuration across refresh', async ({
  page,
  browser,
  baseURL,
}) => {
  await page.setViewportSize({ width: 1672, height: 941 });
  await page.goto('/skills');
  await expect(page.locator('.skill-card')).toHaveCount(13);
  await page.screenshot({ path: '.artifacts/screenshots/slice-2-skills.png', fullPage: true });
  await page.getByRole('button', { name: '基础分析', exact: true }).click();
  await expect(page.locator('.skill-card')).toHaveCount(4);
  await page
    .locator('.skill-card')
    .filter({ has: page.getByRole('heading', { name: /用户评价/ }) })
    .getByRole('link', { name: '详情与配置' })
    .click();
  await expect(page.getByRole('checkbox', { name: '启用此技能' })).toBeChecked();
  await expect(page.getByRole('checkbox', { name: '启用此技能' })).toBeDisabled();
  await page.getByRole('spinbutton', { name: 'review_sample_limit', exact: true }).fill('80');
  const saved = page.waitForResponse(
    (r) => r.url().includes('/user_sentiment/config') && r.request().method() === 'PATCH',
  );
  await page.getByRole('button', { name: '保存配置', exact: true }).click();
  expect((await saved).status()).toBe(200);
  await page.reload();
  await expect(
    page.getByRole('spinbutton', { name: 'review_sample_limit', exact: true }),
  ).toHaveValue('80');
  await page.screenshot({
    path: '.artifacts/screenshots/slice-2-skill-detail.png',
    fullPage: true,
  });
  await page.goto('/');
  await page.getByRole('checkbox', { name: '市场格局分析', exact: true }).check();
  await page.getByRole('link', { name: '管理技能', exact: true }).click();
  await page
    .locator('.skill-card')
    .filter({ has: page.getByRole('heading', { name: /市场格局分析/ }) })
    .getByRole('link', { name: '详情与配置' })
    .click();
  await page.getByRole('checkbox', { name: '启用此技能' }).uncheck();
  const disabled = page.waitForResponse(
    (r) => r.url().includes('/market_landscape/config') && r.request().method() === 'PATCH',
  );
  await page.getByRole('button', { name: '保存配置', exact: true }).click();
  expect((await disabled).status()).toBe(200);
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '工作台', exact: true })
    .click();
  await expect(page.getByRole('checkbox', { name: '市场格局分析', exact: true })).toBeChecked();
  await expect(page.getByLabel('技能计划预览')).toContainText('已在工作空间停用');
  await page.getByRole('checkbox', { name: '市场格局分析', exact: true }).uncheck();
  await expect(page.getByRole('checkbox', { name: '市场格局分析', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '自动选择', exact: true }).click();
  await expect(page.getByLabel('技能计划预览')).toContainText('5 项技能');
  const other = await browser.newContext();
  try {
    const registered = await other.request.post(`${baseURL}/api/v1/auth/register`, {
      headers: { Origin: new URL(baseURL!).origin },
      data: {
        email: `other-skills-${crypto.randomUUID()}@example.com`,
        password: 'Browser-test-passphrase-42',
        display_name: '另一研究员',
      },
    });
    expect(registered.status()).toBe(201);
    const otherPage = await other.newPage();
    await otherPage.goto(`${baseURL}/skills/market_landscape`);
    await expect(otherPage.getByRole('checkbox', { name: '启用此技能' })).toBeChecked();
  } finally {
    await other.close();
  }
  await page.goto('/skills');
  await page.getByRole('textbox', { name: '搜索技能' }).fill('不存在的技能');
  await expect(page.getByText('没有匹配的技能')).toBeVisible();
});

test('mobile skills centre fits viewport and scene selection uses real state', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/skills/ai_llm');
  await page.getByRole('button', { name: '在工作台选择此场景' }).click();
  await expect(page.getByRole('radio', { name: 'AI 与大模型', exact: true })).toBeChecked();
  await page.goto('/skills');
  await expect(page.locator('.skill-card')).toHaveCount(13);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({
    path: '.artifacts/screenshots/slice-2-skills-mobile.png',
    fullPage: true,
  });
});
