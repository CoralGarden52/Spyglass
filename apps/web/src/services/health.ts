import type { components } from '../types/api.generated';

export type Readiness = components['schemas']['ReadinessResponse'];

export async function fetchReadiness(): Promise<Readiness> {
  const response = await fetch('/api/v1/health/ready', {
    signal: AbortSignal.timeout(12_000),
    cache: 'no-store',
  });
  if (!response.ok && response.status !== 503) throw new Error('无法连接 API');
  const body: Readiness = await response.json();
  if (body.schema_version !== 1 || !body.dependencies || !body.providers) {
    throw new Error('API 响应版本不匹配');
  }
  return body;
}
