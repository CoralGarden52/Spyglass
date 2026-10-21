import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../services/client';
import { listRunEvents, streamRunEvents, type RunEvent } from '../../services/runs';
import { EventCursor, terminalEvent } from './events';

type Connection = {
  runId: string;
  status: 'connecting' | 'connected' | 'reconnecting' | 'finished' | 'error';
  error?: string;
};
export function useRunEvents(runId: string | undefined, isActive: boolean, reconnectKey: number) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['run-events', runId],
    queryFn: () => listRunEvents(runId!),
    enabled: !!runId,
    retry: false,
  });
  const [connection, setConnection] = useState<Connection>();
  const ready = !!query.data;
  useEffect(() => {
    if (!runId || !ready || !isActive) return;
    const controller = new AbortController();
    const cursor = new EventCursor(runId);
    for (const event of client.getQueryData<RunEvent[]>(['run-events', runId]) ?? [])
      cursor.accept(event);
    let terminal = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const connect = async (attempt: number) => {
      if (controller.signal.aborted) return;
      setConnection({ runId, status: attempt ? 'reconnecting' : 'connecting' });
      try {
        await streamRunEvents(runId, cursor.afterSeq, controller.signal, (value) => {
          if (controller.signal.aborted) return;
          const event = cursor.accept(value);
          if (!event) return;
          setConnection({ runId, status: 'connected' });
          client.setQueryData<RunEvent[]>(['run-events', runId], (previous = []) => [
            ...previous,
            event,
          ]);
          if (event.type.startsWith('run.') || event.type === 'report.updated') {
            void client.invalidateQueries({ queryKey: ['run', runId] });
            void client.invalidateQueries({ queryKey: ['thread-runs', event.thread_id] });
            void client.invalidateQueries({ queryKey: ['thread-messages', event.thread_id] });
          }
          if (event.type === 'report.updated' || terminalEvent(event.type)) {
            void client.invalidateQueries({ queryKey: ['report'] });
            void client.invalidateQueries({ queryKey: ['project-reports'] });
            void client.invalidateQueries({ queryKey: ['projects'] });
          }
          if (terminalEvent(event.type)) {
            terminal = true;
            setConnection({ runId, status: 'finished' });
          }
        });
        if (!terminal) throw new Error('事件流已断开，正在读取持久化状态');
      } catch (error) {
        if (controller.signal.aborted) return;
        const fatal = error instanceof ApiError && [401, 403, 404, 422].includes(error.status);
        if (attempt < 3 && !fatal) {
          setConnection({ runId, status: 'reconnecting' });
          retry = setTimeout(() => void connect(attempt + 1), 1000 * 2 ** attempt);
        } else
          setConnection({
            runId,
            status: 'error',
            error: error instanceof Error ? error.message : '事件连接失败',
          });
        void client.invalidateQueries({ queryKey: ['run', runId] });
        void client.invalidateQueries({ queryKey: ['thread-runs'] });
        void client.invalidateQueries({ queryKey: ['thread-messages'] });
      }
    };
    void connect(0);
    return () => {
      controller.abort();
      if (retry) clearTimeout(retry);
    };
  }, [runId, ready, isActive, reconnectKey, client]);
  return { ...query, connection: connection?.runId === runId ? connection : undefined };
}
