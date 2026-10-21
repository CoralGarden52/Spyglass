import type { RunEvent } from '../../services/runs';

export type SSEFrame = { id: string; event: string; data: string };
/** Incremental SSE framing; heartbeat comments never become business events. */
export class SSEDecoder {
  private buffer = '';
  push(chunk: string): SSEFrame[] {
    this.buffer += chunk;
    const result: SSEFrame[] = [];
    let boundary: RegExpExecArray | null;
    while ((boundary = /\r?\n\r?\n/.exec(this.buffer))) {
      const frame = this.buffer.slice(0, boundary.index);
      this.buffer = this.buffer.slice(boundary.index + boundary[0].length);
      let id = '';
      let event = 'message';
      const data: string[] = [];
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith(':')) continue;
        const colon = line.indexOf(':');
        const field = colon < 0 ? line : line.slice(0, colon);
        const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
        if (field === 'id') id = value;
        if (field === 'event') event = value;
        if (field === 'data') data.push(value);
      }
      if (data.length) result.push({ id, event, data: data.join('\n') });
    }
    return result;
  }
}

/** A cursor belongs to exactly one Run, including during replay and reconnect. */
export class EventCursor {
  afterSeq = 0;
  private ids = new Set<string>();
  constructor(private runId: string) {}
  accept(value: unknown): RunEvent | null {
    if (!value || typeof value !== 'object') throw new Error('运行事件协议无效');
    const event = value as RunEvent;
    if (
      event.schema_version !== 1 ||
      !Number.isInteger(event.seq) ||
      event.seq < 1 ||
      typeof event.event_id !== 'string' ||
      typeof event.run_id !== 'string' ||
      typeof event.thread_id !== 'string' ||
      typeof event.type !== 'string' ||
      typeof event.timestamp !== 'string' ||
      !event.payload ||
      typeof event.payload !== 'object' ||
      Array.isArray(event.payload)
    ) {
      throw new Error('运行事件协议无效');
    }
    if (event.run_id !== this.runId || event.seq <= this.afterSeq || this.ids.has(event.event_id))
      return null;
    this.ids.add(event.event_id);
    this.afterSeq = event.seq;
    return event;
  }
}

export const terminalEvent = (type: string) =>
  ['run.completed', 'run.failed', 'run.cancelled', 'run.needs_review'].includes(type);
