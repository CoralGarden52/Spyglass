import type { RunEvent } from '../../services/runs';
const phases = [
  ['planner', '需求理解'],
  ['resolver', '技能解析'],
  ['collector', '信息采集'],
  ['normalizer', '结构化整理'],
  ['analyse', '竞品分析'],
  ['writer', '报告撰写'],
  ['reviewer', '质量审查'],
] as const;
export function deriveStages(events: RunEvent[]) {
  return phases.map(([node, label]) => {
    let relevant = events;
    let completed = false;
    if (node === 'analyse') {
      const start =
        [...events]
          .reverse()
          .find((e) => e.payload.node === 'analyse' && e.type === 'agent.started')?.seq ?? 0;
      relevant = events.filter(
        (e) =>
          e.seq >= start &&
          ['analyse', 'product', 'pricing', 'sentiment', 'synthesis'].includes(
            String(e.payload.node),
          ),
      );
      completed = relevant.some(
        (e) =>
          e.payload.node === 'synthesis' &&
          e.type === 'agent.completed' &&
          !['failed', 'cancelled'].includes(String(e.payload.status)),
      );
    }
    const last = [...relevant]
      .reverse()
      .find(
        (event) =>
          (node === 'analyse' || event.payload.node === node) &&
          ['agent.started', 'agent.completed'].includes(event.type),
      );
    const status = !last
      ? 'waiting'
      : last.payload.status === 'failed'
        ? 'failed'
        : last.payload.status === 'cancelled'
          ? 'cancelled'
          : node === 'analyse'
            ? completed
              ? 'completed'
              : 'running'
            : last.type === 'agent.started'
              ? 'running'
              : 'completed';
    return { node, label, status };
  });
}
