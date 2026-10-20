import { expect, test } from '@playwright/test';

test('revoked sessions cannot carry a private draft into a different account', async ({
  page,
  baseURL,
}) => {
  const origin = new URL(baseURL!).origin;
  const response = await page.request.post('/api/v1/auth/register', {
    headers: { Origin: origin },
    data: {
      email: `alice-${crypto.randomUUID()}@example.com`,
      password: 'Browser-test-passphrase-42',
      display_name: 'Alice',
    },
  });
  expect(response.status()).toBe(201);
  await page.goto('/');
  await page
    .getByRole('textbox', { name: '研究目标' })
    .fill('ALICE PRIVATE SYNTHETIC RESEARCH DRAFT');
  await page.getByRole('button', { name: '深度调研', exact: true }).click();
  const cookies = await page.context().cookies();
  const revoked = await page.request.post('/api/v1/auth/logout', {
    headers: {
      Origin: origin,
      'X-CSRF-Token': cookies.find((cookie) => cookie.name === 'sg_csrf')!.value,
    },
  });
  expect(revoked.status()).toBe(204);
  await page.getByRole('link', { name: '账户设置' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole('link', { name: '创建账户' }).click();
  await page.getByRole('textbox', { name: '姓名' }).fill('Bob');
  await page.getByRole('textbox', { name: '邮箱' }).fill(`bob-${crypto.randomUUID()}@example.com`);
  await page.getByLabel('密码', { exact: true }).fill('Browser-test-passphrase-42');
  await page.getByRole('button', { name: '注册并进入工作台' }).click();
  await expect(page.getByRole('heading', { name: '你好，Bob' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: '研究目标' })).toHaveValue('');
  await expect(page.getByRole('button', { name: '标准调研', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
});

test('registration, refresh restoration and logout use a real database session', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole('link', { name: '创建账户' }).click();
  await page.getByRole('textbox', { name: '姓名' }).fill('林研究员');
  const email = `ui-${crypto.randomUUID()}@example.com`;
  await page.getByRole('textbox', { name: '邮箱' }).fill(email);
  await page.getByLabel('密码', { exact: true }).fill('Browser-test-passphrase-42');
  await expect(page.locator('.auth-card')).toHaveCSS('opacity', '1');
  await page.screenshot({ path: '.artifacts/screenshots/slice-1-register.png', fullPage: true });
  await page.getByRole('button', { name: '注册并进入工作台' }).click();
  await expect(page.getByRole('heading', { name: '你好，林研究员' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '你好，林研究员' })).toBeVisible();
  await page.getByRole('link', { name: '账户设置' }).click();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole('textbox', { name: '邮箱' }).fill(email);
  await page.getByLabel('密码', { exact: true }).fill('Wrong-test-passphrase-42');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('邮箱或密码不正确');
  await page.getByLabel('密码', { exact: true }).fill('Browser-test-passphrase-42');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('heading', { name: '你好，林研究员' })).toBeVisible();
});

test('project creation persists, searches and stays private to its account', async ({
  page,
  browser,
  baseURL,
}) => {
  const response = await page.request.post('/api/v1/auth/register', {
    headers: { Origin: new URL(baseURL!).origin },
    data: {
      email: `project-${crypto.randomUUID()}@example.com`,
      password: 'Browser-test-passphrase-42',
      display_name: '项目研究员',
    },
  });
  expect(response.status()).toBe(201);
  await page.goto('/research');
  await expect(page.getByRole('heading', { name: '尚未创建调研项目' })).toBeVisible();
  await page.getByRole('button', { name: '创建项目', exact: true }).click();
  await page.getByRole('textbox', { name: '项目名称' }).fill('AI 编程工具研究');
  await page.getByRole('button', { name: '保存项目' }).click();
  await page.getByRole('link', { name: /AI 编程工具研究/ }).click();
  const privateUrl = page.url();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'AI 编程工具研究', exact: true })).toBeVisible();
  await page.screenshot({ path: '.artifacts/screenshots/slice-1-project.png', fullPage: true });
  const other = await browser.newContext();
  const otherPage = await other.newPage();
  const registration = await other.request.post(`${baseURL}/api/v1/auth/register`, {
    headers: { Origin: new URL(baseURL!).origin },
    data: {
      email: `other-${crypto.randomUUID()}@example.com`,
      password: 'Browser-test-passphrase-42',
      display_name: '另一研究员',
    },
  });
  expect(registration.status()).toBe(201);
  await otherPage.goto(privateUrl);
  await expect(otherPage.getByRole('heading', { name: '项目不存在或无权访问' })).toBeVisible();
  await other.close();
  await page.getByRole('link', { name: /返回我的调研/ }).click();
  await page.getByRole('textbox', { name: '搜索调研项目' }).fill('没有这个项目');
  await page.getByRole('button', { name: '搜索', exact: true }).click();
  await expect(page.getByRole('heading', { name: '没有找到匹配项目' })).toBeVisible();
});
