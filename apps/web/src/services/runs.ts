import type { components } from '../types/api.generated';
import { ApiError, request } from './client';
import { SSEDecoder } from '../features/runs/events';

export type RunView = components['schemas']['RunView'];
export type RunEvent = components['schemas']['RunEventView'];
export type RunInput = components['schemas']['RunRequest'];
export type RunResponse = components['schemas']['RunCreated'];
export type ThreadView = components['schemas']['ThreadView'];
export const createThread = (projectId: string, title: string, key: string) =>
  request<components['schemas']['ThreadResult']>('/threads', {
    method: 'POST',
    headers: { 'Idempotency-Key': key },
    body: JSON.stringify({ project_id: projectId, title }),
  });
export const listThreads = (projectId: string) =>
  request<components['schemas']['ThreadList']>(
    `/research/${encodeURIComponent(projectId)}/threads`,
  );
export const getThread = (id: string) =>
  request<components['schemas']['ThreadResult']>(`/threads/${encodeURIComponent(id)}`);
export const listMessages = (id: string) =>
  request<components['schemas']['MessageList']>(`/threads/${encodeURIComponent(id)}/messages`);
export const createRun = (id: string, input: RunInput, key: string) =>
  request<RunResponse>(`/threads/${encodeURIComponent(id)}/runs`, {
    method: 'POST',
    headers: { 'Idempotency-Key': key },
    body: JSON.stringify(input),
  });
export const listRuns = (id: string) =>
  request<components['schemas']['RunList']>(`/threads/${encodeURIComponent(id)}/runs`);
export const getRun = (id: string) =>
  request<components['schemas']['RunResponse']>(`/runs/${encodeURIComponent(id)}`);
export const cancelRun = (id: string, key: string) =>
  request<components['schemas']['RunResponse']>(`/runs/${encodeURIComponent(id)}/cancel`, {
    method: 'POST',
    headers: { 'Idempotency-Key': key },
    body: '{}',
  });
export const activeRun = (run?: RunView) =>
  !!run && ['pending', 'running', 'cancel_requested', 'waiting_approval'].includes(run.status);
export async function listRunEvents(id: string): Promise<RunEvent[]> {
  const events: RunEvent[] = [];
  let after = 0;
  for (;;) {
    const result = await request<components['schemas']['EventList']>(
      `/runs/${encodeURIComponent(id)}/events/history?after_seq=${after}&limit=500`,
    );
    events.push(...result.data);
    if (result.data.length < 500) return events;
    const next = result.data.at(-1)!.seq;
    if (next <= after) throw new Error('运行事件游标未前进');
    after = next;
  }
}
export async function streamRunEvents(
  id: string,
  afterSeq: number,
  signal: AbortSignal,
  receive: (value: unknown) => void,
) {
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(id)}/events?after_seq=${afterSeq}`,
    { credentials: 'include', signal, headers: { Accept: 'text/event-stream' } },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'stream_error',
      body?.error?.message ?? '事件连接失败',
    );
  }
  if (!response.body) throw new Error('浏览器不支持事件流');
  const reader = response.body.getReader();
  const utf8 = new TextDecoder();
  const decoder = new SSEDecoder();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const frame of decoder.push(utf8.decode(value, { stream: true }))) {
        const value: unknown = JSON.parse(frame.data);
        if (frame.id && (value as RunEvent)?.event_id !== frame.id)
          throw new Error('运行事件标识不一致');
        receive(value);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
