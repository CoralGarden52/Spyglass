import {
  Bot,
  CheckCircle2,
  ChevronDown,
  Clock3,
  FileSearch,
  Info,
  LoaderCircle,
  Search,
  Sparkles,
  XCircle,
} from 'lucide-react';
import { activeRun, type RunEvent, type RunView } from '../../services/runs';

function compact(value: number | undefined) {
  return value == null ? '—' : value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(value);
}

export function RunActivity({ events, run }: { events: RunEvent[]; run?: RunView }) {
  const calls = events.filter((e) => e.type === 'model.completed');
  const total = (key: string) =>
    calls.length &&
    calls.every(
      (e) => typeof (e.payload.usage as Record<string, unknown> | null)?.[key] === 'number',
    )
      ? calls.reduce((sum, e) => sum + (e.payload.usage as Record<string, number>)[key], 0)
      : undefined;
  const plan = [...events].reverse().find((e) => e.type === 'plan.updated');
  const competitors = Array.isArray(plan?.payload.competitor_names)
    ? plan.payload.competitor_names.filter((name): name is string => typeof name === 'string')
    : [];
  const searches = events
    .filter((e) => e.type === 'tool.started' && e.payload.name === 'deepseek_search')
    .map((start) => {
      const end = events.find(
        (e) => e.type === 'tool.completed' && e.payload.tool_call_id === start.payload.tool_call_id,
      );
      const args = start.payload.arguments as Record<string, unknown> | null;
      return { start, end, query: typeof args?.query === 'string' ? args.query : '公开资料检索' };
    });
  const collecting = activeRun(run);
  const renderSearch = ({ start, end, query }: (typeof searches)[number]) => (
    <li key={start.event_id}>
      <span className={`activity-indicator ${end?.payload.status === 'failed' ? 'has-error' : ''}`}>
        {end ? (
          end.payload.status === 'completed' ? (
            <CheckCircle2 size={17} />
          ) : (
            <XCircle size={17} />
          )
        ) : collecting ? (
          <LoaderCircle size={17} className="is-spinning" />
        ) : (
          <XCircle size={17} />
        )}
      </span>
      <div>
        <strong>{query}</strong>
        <small>
          {end
            ? typeof end.payload.result_count === 'number'
              ? `返回 ${end.payload.result_count} 个候选来源`
              : '检索已结束'
            : collecting
              ? '正在检索公开来源…'
              : '已中断，未收到结束事件'}
        </small>
      </div>
      <span className="activity-tool-tag">
        <Search size={11} />
        联网检索
      </span>
      <span className="activity-time">
        {end
          ? `${((new Date(end.timestamp).getTime() - new Date(start.timestamp).getTime()) / 1000).toFixed(1)}s`
          : collecting
            ? '进行中'
            : '—'}
      </span>
    </li>
  );
  const duration =
    run?.started_at && run.finished_at
      ? ((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(
          1,
        ) + 's'
      : '—';
  return (
    <>
      <details className="phase-usage">
        <summary>
          <span className="phase-usage-label">
            <FileSearch size={17} />
            <strong>本轮模型用量</strong>
            <Info size={12} />
          </span>
          <span>
            输入 <b>{compact(total('prompt_tokens'))}</b>
          </span>
          <span>
            输出 <b>{compact(total('completion_tokens'))}</b>
          </span>
          <span>
            Token{' '}
            <b>
              {compact(
                typeof run?.usage_json?.total_tokens === 'number'
                  ? run.usage_json.total_tokens
                  : total('total_tokens'),
              )}
            </b>
          </span>
          <span className="usage-duration">
            <Clock3 size={12} />
            {duration}
          </span>
          <ChevronDown size={13} className="usage-chevron" />
        </summary>
        <div className="usage-call-list">
          <p>仅汇总供应商实际返回的用量；存在未知项时显示 —。耗时来自本轮已保存的起止时间。</p>
          {calls.map((call) => (
            <div key={call.event_id}>
              <strong>{String(call.payload.name)}</strong>
              <span>{String(call.payload.model ?? '模型未知')}</span>
              <span>
                {compact(
                  typeof (call.payload.usage as Record<string, unknown> | null)?.total_tokens ===
                    'number'
                    ? (call.payload.usage as Record<string, number>).total_tokens
                    : undefined,
                )}{' '}
                Token
              </span>
              <small>{String(call.payload.prompt_version ?? '')}</small>
            </div>
          ))}
        </div>
      </details>
      {searches.length > 0 && (
        <section className="collection-activity" aria-label="信息采集任务">
          <header>
            <span className="agent-icon">
              <Bot size={19} />
            </span>
            <strong>信息采集智能体</strong>
            <span>
              {collecting && searches.some((s) => !s.end)
                ? '正在检索与整理信息…'
                : `${searches.length} 次检索已记录`}
            </span>
            <span className="collection-live-dot" />
          </header>
          <ul>{searches.slice(-4).map(renderSearch)}</ul>
          {searches.length > 4 && (
            <details>
              <summary>
                查看其余 {searches.length - 4} 次检索
                <ChevronDown size={13} />
              </summary>
              <ul>{searches.slice(0, -4).map(renderSearch)}</ul>
            </details>
          )}
        </section>
      )}
      {competitors.length > 0 && (
        <section className="research-scope">
          <h3>
            <Sparkles size={16} />
            本轮研究范围
          </h3>
          <div>
            {competitors.map((name) => (
              <span key={name}>
                <span className="scope-initial">{name.slice(0, 1)}</span>
                {name}
              </span>
            ))}
          </div>
          {typeof plan?.payload.scope === 'string' && <p>{plan.payload.scope}</p>}
        </section>
      )}
    </>
  );
}
