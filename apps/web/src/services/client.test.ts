import { afterEach, expect, test, vi } from 'vitest';
import { ApiError, request } from './client';

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'sg_csrf=; max-age=0; path=/';
});

test('authenticated writes include cookies and the session-bound csrf token', async () => {
  document.cookie = 'sg_csrf=test-csrf; path=/';
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal('fetch', fetchMock);
  await request('/auth/logout', { method: 'POST' });
  const options = fetchMock.mock.calls[0][1] as RequestInit;
  expect(options.credentials).toBe('include');
  expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('test-csrf');
});

test('errors preserve the public code and request id for useful feedback', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: 'rate_limited', message: '稍后重试', request_id: 'test-request-id' },
        }),
        { status: 429 },
      ),
    ),
  );
  await expect(request('/auth/login', { method: 'POST' })).rejects.toMatchObject({
    status: 429,
    code: 'rate_limited',
    requestId: 'test-request-id',
  });
});

test('unexpected upstream responses still return a controlled API error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 502 })));
  await expect(request('/research')).rejects.toBeInstanceOf(ApiError);
});
