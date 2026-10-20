import type { components } from '../types/api.generated';

type ErrorBody = components['schemas']['ErrorResponse'];

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set('Content-Type', 'application/json');
  if (options.method && options.method !== 'GET') {
    const cookie = document.cookie.split('; ').find((value) => value.startsWith('sg_csrf='));
    if (cookie) headers.set('X-CSRF-Token', decodeURIComponent(cookie.slice(8)));
  }
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: 'include',
    signal: options.signal ?? AbortSignal.timeout(15_000),
  });
  if (!response.ok) {
    const body: ErrorBody | null = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'network_error',
      body?.error?.message ?? '请求失败，请稍后重试',
      body?.error?.request_id,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
