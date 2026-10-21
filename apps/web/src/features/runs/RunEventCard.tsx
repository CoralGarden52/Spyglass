import type { RunEvent } from '../../services/runs';

const names: Record<string, string> = {
  'run.started': '研究开始',
  'run.completed': '研究完成',
  'run.failed': '研究失败',
  'run.cancelled': '研究已取消',
  'run.cancel_requested': '正在取消研究',
  'evidence.added': '来源证据已保存',
  'review.failed': '质检发现问题',
  'review.completed': '质检完成',
  'run.needs_review': '研究需复核',
  'plan.updated': '研究计划已生成',
  'source.updated': '来源已更新',
  'sources.updated': '来源已更新',
  'analysis.updated': '分析产物已更新',
  'report.updated': '报告已保存',
  'review.updated': '质检结果已更新',
  'agent.started': '开始执行',
  'agent.completed': '步骤结束',
  'tool.started': '调用工具',
  'tool.completed': '工具调用结束',
  'model.completed': '模型调用结束',
};
const nodes: Record<string, string> = {
  planner: '需求理解',
  resolver: '技能解析',
  collector: '信息采集',
  normalizer: '结构化整理',
  analyse: '竞品分析',
  product: '产品能力',
  pricing: '定价策略',
  sentiment: '用户评价',
  synthesis: 'SWOT 与增强分析',
  writer: '报告撰写',
  reviewer: '质量审查',
};
export function RunEventCard({ event }: { event: RunEvent }) {
  const data = event.payload;
  const node = typeof data.node === 'string' ? (nodes[data.node] ?? data.node) : '';
  const name = typeof data.name === 'string' ? data.name : '';
  return (
    <li className={`run-event ${event.type.startsWith('tool.') ? 'tool-event' : ''}`}>
      <span className="event-dot" />
      <div>
        <div className="event-heading">
          <strong>
            {node}
            {node ? ' · ' : ''}
            {names[event.type] ?? event.type}
            {name ? ` · ${name}` : ''}
          </strong>
          <time dateTime={event.timestamp}>
            {new Date(event.timestamp).toLocaleTimeString('zh-CN')}
          </time>
        </div>
        {Array.isArray(data.competitor_names) && (
          <p className="muted">
            研究对象：{data.competitor_names.filter((v) => typeof v === 'string').join('、')}
          </p>
        )}
        {typeof data.scope === 'string' && <p>{data.scope}</p>}
        {typeof data.skill_id === 'string' && (
          <p className="muted">
            {data.skill_id}
            {typeof data.revision === 'number' ? ` · 修订 ${data.revision}` : ''}
          </p>
        )}
        {typeof data.status === 'string' && (
          <span className="small-badge">
            {(
              {
                completed: '已完成',
                succeeded: '成功',
                failed: '失败',
                passed: '通过',
                repair: '定向返工',
                needs_review: '需复核',
                partial: '部分结果',
                insufficient_evidence: '证据不足',
              } as Record<string, string>
            )[data.status] ?? data.status}
          </span>
        )}
        {typeof data.result_count === 'number' && (
          <span className="muted"> · 返回 {data.result_count} 条结果</span>
        )}
        {typeof data.error_code === 'string' && <p className="form-error">{data.error_code}</p>}
        <details>
          <summary>事件详情</summary>
          {typeof data.arguments === 'object' &&
            data.arguments !== null &&
            'query' in data.arguments &&
            typeof data.arguments.query === 'string' && <p>检索 Query：{data.arguments.query}</p>}
          <p className="muted">
            序号 {event.seq} · {event.type}
            <br />
            事件 ID：{event.event_id}
          </p>
        </details>
      </div>
    </li>
  );
}
