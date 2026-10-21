import { afterEach, expect, test, vi } from 'vitest';
import { launchResearch, newLaunchAttempt } from './launch';
import type { RunInput } from './runs';

const input: RunInput = {
  user_message: 'Compare public products',
  mode: 'standard',
  scenario_skill_id: 'ai_llm',
  advanced_skill_ids: ['market_landscape'],
  advanced_skill_selection: 'manual',
};
const stamp = '2026-10-20T01:00:00Z';
const project = {
  schema_version: 1,
  data: {
    id: 'project',
    tenant_id: 'tenant',
    title: input.user_message,
    status: 'draft',
    mode: 'standard',
    scenario_skill_id: 'ai_llm',
    created_at: stamp,
    updated_at: stamp,
  },
};
const thread = {
  schema_version: 1,
  data: {
    id: 'thread',
    project_id: 'project',
    tenant_id: 'tenant',
    title: input.user_message,
    created_at: stamp,
  },
};
const run = {
  schema_version: 1,
  data: {
    id: 'run',
    thread_id: 'thread',
    project_id: 'project',
    status: 'pending',
    error_code: null,
    requested_at: stamp,
    started_at: null,
    finished_at: null,
    usage_json: null,
    report_id: null,
    selection: input,
  },
  events_url: '/runs/run/events',
};
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => vi.unstubAllGlobals());

test('a provider rejection retries the same Run without creating another project or thread', async () => {
  const seen: { path: string; key: string | null; body: unknown }[] = [];
  let rejected = false;
  vi.stubGlobal('fetch', async (path: string, options: RequestInit) => {
    seen.push({
      path,
      key: new Headers(options.headers).get('Idempotency-Key'),
      body: JSON.parse(options.body as string),
    });
    if (path === '/api/v1/research') return response(project);
    if (path === '/api/v1/threads') return response(thread);
    if (!rejected) {
      rejected = true;
      return response(
        { error: { code: 'provider_unavailable', message: 'Unavailable', request_id: 'request' } },
        503,
      );
    }
    return response(run);
  });
  const attempt = newLaunchAttempt(input);
  await expect(launchResearch(attempt)).rejects.toThrow('Unavailable');
  expect(await launchResearch(attempt)).toMatchObject({ threadId: 'thread', run: { id: 'run' } });
  expect(seen.map((item) => item.path)).toEqual([
    '/api/v1/research',
    '/api/v1/threads',
    '/api/v1/threads/thread/runs',
    '/api/v1/threads/thread/runs',
  ]);
  expect(seen[2].key).toBe(seen[3].key);
  expect(seen[3].body).toEqual(input);
});

test('an uncertain thread response retains its idempotency key across retry', async () => {
  const seen: { path: string; key: string | null }[] = [];
  let lost = false;
  vi.stubGlobal('fetch', async (path: string, options: RequestInit) => {
    seen.push({ path, key: new Headers(options.headers).get('Idempotency-Key') });
    if (path === '/api/v1/research') return response(project);
    if (path === '/api/v1/threads' && !lost) {
      lost = true;
      throw new TypeError('Connection lost');
    }
    if (path === '/api/v1/threads') return response(thread);
    return response(run);
  });
  const attempt = newLaunchAttempt(input);
  await expect(launchResearch(attempt)).rejects.toThrow('Connection lost');
  await launchResearch(attempt);
  expect(seen.map((item) => item.path)).toEqual([
    '/api/v1/research',
    '/api/v1/threads',
    '/api/v1/threads',
    '/api/v1/threads/thread/runs',
  ]);
  expect(seen[1].key).toBe(seen[2].key);
});
