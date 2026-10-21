import { render, screen } from '@testing-library/react';
import { RunActivity } from './RunActivity';
import type { RunEvent, RunView } from '../../services/runs';

const run: RunView = {
  id: 'run',
  thread_id: 'thread',
  project_id: 'project',
  status: 'cancelled',
  error_code: 'run_cancelled',
  requested_at: '2026-10-21T00:00:00Z',
  started_at: '2026-10-21T00:00:00Z',
  finished_at: '2026-10-21T00:00:05Z',
  usage_json: null,
};
const event = (seq: number, type: string, payload: Record<string, unknown>): RunEvent => ({
  event_id: String(seq),
  schema_version: 1,
  seq,
  run_id: 'run',
  thread_id: 'thread',
  timestamp: '2026-10-21T00:00:00Z',
  type,
  payload,
});

test('a terminal run never displays a missing tool-end event as ongoing collection', () => {
  render(
    <RunActivity
      run={run}
      events={[
        event(1, 'tool.started', {
          name: 'deepseek_search',
          tool_call_id: 'tool',
          arguments: { query: 'Controlled arbitrary product' },
        }),
      ]}
    />,
  );
  expect(screen.getByText('已中断，未收到结束事件')).toBeInTheDocument();
  expect(screen.queryByText('正在检索公开来源…')).not.toBeInTheDocument();
});

test('unknown model usage prevents presenting a partial sum as a complete total', () => {
  const { container } = render(
    <RunActivity
      run={run}
      events={[
        event(1, 'model.completed', {
          usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
        }),
        event(2, 'model.completed', { usage: null }),
      ]}
    />,
  );
  const summary = container.querySelector('.phase-usage > summary')!;
  expect(summary).toHaveTextContent('输入 —');
  expect(summary).toHaveTextContent('输出 —');
  expect(summary).toHaveTextContent('Token —');
  expect(summary).toHaveTextContent('5.0s');
});
