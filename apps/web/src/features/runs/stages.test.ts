import { expect, test } from 'vitest';
import { deriveStages } from './stages';
import type { RunEvent } from '../../services/runs';
const event = (seq: number, type: string, node: string): RunEvent => ({
  event_id: `event-${seq}`,
  schema_version: 1,
  seq,
  run_id: 'run',
  thread_id: 'thread',
  type,
  timestamp: '2026-10-20T01:00:00Z',
  payload: { node },
});
test('stages change only with persisted agent events, including a repair restart', () => {
  expect(deriveStages([]).map((stage) => stage.status)).toEqual([
    'waiting',
    'waiting',
    'waiting',
    'waiting',
    'waiting',
    'waiting',
    'waiting',
  ]);
  const events = [event(1, 'agent.completed', 'planner'), event(2, 'agent.started', 'collector')];
  expect(deriveStages(events).find((stage) => stage.node === 'collector')?.status).toBe('running');
  expect(
    deriveStages([
      ...events,
      event(3, 'agent.completed', 'collector'),
      event(4, 'agent.started', 'collector'),
    ]).find((stage) => stage.node === 'collector')?.status,
  ).toBe('running');
  expect(deriveStages(events).find((stage) => stage.node === 'writer')?.status).toBe('waiting');
});

test('analysis remains running until all parallel branches and synthesis finish', () => {
  const events = [
    event(1, 'agent.started', 'analyse'),
    event(2, 'agent.completed', 'analyse'),
    event(3, 'agent.started', 'product'),
    event(4, 'agent.started', 'pricing'),
    event(5, 'agent.started', 'sentiment'),
  ];
  const status = (items: RunEvent[]) =>
    deriveStages(items).find((s) => s.node === 'analyse')?.status;
  expect(status(events)).toBe('running');
  events.push(
    event(6, 'agent.completed', 'product'),
    event(7, 'agent.completed', 'pricing'),
    event(8, 'agent.completed', 'sentiment'),
    event(9, 'agent.started', 'synthesis'),
  );
  expect(status(events)).toBe('running');
  events.push(event(10, 'agent.completed', 'synthesis'));
  expect(status(events)).toBe('completed');
  events.push(event(11, 'agent.started', 'analyse'));
  expect(status(events)).toBe('running');
});

test('a cancelled node does not appear completed', () => {
  const cancelled = event(1, 'agent.completed', 'collector');
  cancelled.payload.status = 'cancelled';
  expect(deriveStages([cancelled]).find((s) => s.node === 'collector')?.status).toBe('cancelled');
});
