import { describe, expect, test } from 'vitest';
import { EventCursor, SSEDecoder } from './events';

const event = (seq: number, runId = 'run-a', id = `event-${seq}`) => ({
  event_id: id,
  schema_version: 1,
  seq,
  run_id: runId,
  thread_id: 'thread-a',
  type: 'agent.completed',
  timestamp: '2026-10-20T01:00:00Z',
  payload: { agent: 'collector' },
});

describe('persistent run event adapter', () => {
  test('decodes split CRLF frames, ignores heartbeats and preserves multiline data', () => {
    const decoder = new SSEDecoder();
    expect(
      decoder.push(
        ': heartbeat\r\n\r\nid: event-1\r\nevent: agent.completed\r\ndata: {"schema_version":1,\r',
      ),
    ).toEqual([]);
    expect(decoder.push('\ndata: "seq":1}\r\n\r\n')).toEqual([
      { id: 'event-1', event: 'agent.completed', data: '{"schema_version":1,\n"seq":1}' },
    ]);
  });
  test('replay suppresses duplicate IDs and sequences without advancing another run', () => {
    const cursor = new EventCursor('run-a');
    expect(cursor.accept(event(1))).toEqual(event(1));
    expect(cursor.accept(event(2, 'run-b'))).toBeNull();
    expect(cursor.accept(event(2, 'run-a', 'event-1'))).toBeNull();
    expect(cursor.afterSeq).toBe(1);
    expect(cursor.accept(event(1, 'run-a', 'different-id'))).toBeNull();
    expect(cursor.accept(event(2))).toEqual(event(2));
    expect(cursor.afterSeq).toBe(2);
    const otherRun = new EventCursor('run-b');
    expect(otherRun.accept(event(1, 'run-b'))?.seq).toBe(1);
  });
  test('rejects invalid schemas and malformed payloads with visible errors', () => {
    const cursor = new EventCursor('run-a');
    expect(() => cursor.accept({ ...event(1), schema_version: 2 })).toThrow('事件协议');
    expect(() => cursor.accept({ ...event(1), seq: -1 })).toThrow('事件协议');
    expect(() => cursor.accept({ ...event(1), payload: null })).toThrow('事件协议');
    expect(cursor.afterSeq).toBe(0);
  });
});
