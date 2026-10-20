import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import { HealthStatus } from './HealthStatus';

afterEach(() => vi.unstubAllGlobals());

function renderStatus() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <HealthStatus />
    </QueryClientProvider>,
  );
}

test('shows real dependency state without claiming provider connectivity', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          schema_version: 1,
          status: 'ready',
          dependencies: { postgres: 'ok', redis: 'ok', pgvector: 'ok', migrations: 'ok' },
          providers: { deepseek: 'configured', bocha: 'unconfigured' },
          research_available: false,
        }),
      ),
    ),
  );
  renderStatus();
  expect(await screen.findByText('基础服务已就绪')).toBeInTheDocument();
  expect(screen.getByText(/DeepSeek 已配置（未验证连通）/)).toBeInTheDocument();
  expect(screen.getByText(/Bocha 未配置/)).toBeInTheDocument();
  expect(screen.getByText(/研究链路尚未开放/)).toBeInTheDocument();
});

test('shows dependency failures returned with HTTP 503', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          schema_version: 1,
          status: 'degraded',
          dependencies: {
            postgres: 'unavailable',
            redis: 'ok',
            pgvector: 'unavailable',
            migrations: 'unavailable',
          },
          providers: { deepseek: 'unconfigured', bocha: 'unconfigured' },
          research_available: false,
        }),
        { status: 503 },
      ),
    ),
  );
  renderStatus();
  expect(await screen.findByText('基础服务需要检查')).toBeInTheDocument();
  expect(screen.getByText('PostgreSQL 不可用')).toBeInTheDocument();
});

test('network errors offer a working retry action', async () => {
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new Error('network'))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          schema_version: 1,
          status: 'ready',
          dependencies: { postgres: 'ok', redis: 'ok', pgvector: 'ok', migrations: 'ok' },
          providers: { deepseek: 'unconfigured', bocha: 'unconfigured' },
          research_available: false,
        }),
      ),
    );
  vi.stubGlobal('fetch', fetch);
  renderStatus();
  expect(await screen.findByText('无法连接 API')).toBeInTheDocument();
  (await screen.findByRole('button', { name: '重新检查' })).click();
  expect(await screen.findByText('基础服务已就绪')).toBeInTheDocument();
});
