import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useOutletContext, useParams } from 'react-router';
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Compass,
  Download,
  Globe,
  Menu,
  RefreshCw,
  Share2,
  Shapes,
  Sparkles,
  Square,
  UserRound,
} from 'lucide-react';
import { getProject } from '../services/research';
import { activeRun, cancelRun, getRun, getThread, listMessages, listRuns } from '../services/runs';
import { SavedReport } from '../features/reports/ProjectReports';
import { RunComposer } from '../features/runs/RunComposer';
import { CancelDialog } from '../features/runs/CancelDialog';
import { RunEventCard } from '../features/runs/RunEventCard';
import { useRunEvents } from '../features/runs/useRunEvents';
import { StageTimeline } from '../features/runs/StageTimeline';
import { RunActivity } from '../features/runs/RunActivity';

const statuses: Record<string, string> = {
  pending: '等待执行',
  running: '研究进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  needs_review: '需复核',
  cancel_requested: '正在取消',
  waiting_approval: '等待确认',
};
const connectionNames = {
  connecting: '正在连接实时事件…',
  connected: '实时事件已连接',
  reconnecting: '连接中断，正在重连…',
  finished: '实时事件已接收完毕',
  error: '实时连接失败',
};
export function ResearchSession() {
  const { id = '' } = useParams();
  const { openNavigation } = useOutletContext<{ openNavigation: () => void }>();
  const client = useQueryClient();
  const [chosen, setChosen] = useState<{ threadId: string; runId: string }>();
  const [panel, setPanel] = useState<'conversation' | 'report'>('conversation');
  const [reportTab, setReportTab] = useState<'outline' | 'content' | 'sources'>('content');
  const [confirm, setConfirm] = useState(false);
  const [reconnect, setReconnect] = useState(0);
  const cancellationKey = useRef(crypto.randomUUID());
  const thread = useQuery({ queryKey: ['thread', id], queryFn: () => getThread(id), retry: false });
  const projectId = thread.data?.data.project_id;
  const project = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
    retry: false,
  });
  const messages = useQuery({
    queryKey: ['thread-messages', id],
    queryFn: () => listMessages(id),
    retry: false,
  });
  const runs = useQuery({
    queryKey: ['thread-runs', id],
    queryFn: () => listRuns(id),
    retry: false,
  });
  const sortedRuns = [...(runs.data?.data ?? [])].sort((a, b) =>
    b.requested_at.localeCompare(a.requested_at),
  );
  const runId = chosen?.threadId === id ? chosen.runId : sortedRuns[0]?.id;
  const runQuery = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId!),
    enabled: !!runId,
    retry: false,
  });
  const run = runQuery.data?.data ?? sortedRuns.find((r) => r.id === runId);
  const events = useRunEvents(runId, activeRun(run), reconnect);
  const runStatus = run?.status;
  useEffect(() => {
    if (
      !runId ||
      !runStatus ||
      ['pending', 'running', 'cancel_requested', 'waiting_approval'].includes(runStatus)
    )
      return;
    void client.invalidateQueries({ queryKey: ['thread-messages', id] });
    void client.invalidateQueries({ queryKey: ['run-events', runId] });
  }, [runId, runStatus, id, client]);
  const reportId =
    run?.report_id ??
    [...(events.data ?? [])]
      .reverse()
      .map((event) => event.payload.report_id)
      .find((value) => typeof value === 'string');
  const cancel = useMutation({
    mutationFn: () => cancelRun(runId!, cancellationKey.current),
    onSuccess: ({ data }) => {
      client.setQueryData(['run', data.id], { schema_version: 1, data });
      void client.invalidateQueries({ queryKey: ['thread-runs', id] });
      void client.invalidateQueries({ queryKey: ['thread-messages', id] });
      void client.invalidateQueries({ queryKey: ['run-events', data.id] });
      setConfirm(false);
    },
  });
  const refresh = () => {
    void thread.refetch();
    void messages.refetch();
    void runs.refetch();
    if (runId) {
      void runQuery.refetch();
      void events.refetch();
    }
    if (typeof reportId === 'string')
      void client.invalidateQueries({ queryKey: ['report', reportId] });
    setReconnect((value) => value + 1);
  };
  if (thread.isPending)
    return (
      <main className="route-state" role="status">
        正在读取研究会话…
      </main>
    );
  if (thread.error)
    return (
      <main className="route-state" role="alert">
        <h1>会话无法读取</h1>
        <p>{thread.error.message}</p>
        <button className="outline-button" onClick={() => void thread.refetch()}>
          重试
        </button>
        <Link to="/research" className="text-button">
          返回项目
        </Link>
      </main>
    );
  return (
    <main className="research-session">
      <header className="session-heading">
        <div className="session-title-group">
          <button
            className="icon-button session-nav-toggle"
            aria-label="打开导航"
            onClick={openNavigation}
          >
            <Menu size={19} />
          </button>
          <Link
            to={`/research/${projectId}`}
            className="session-project-link"
            aria-label="返回项目"
          >
            <Shapes size={18} />
          </Link>
          <h1>{thread.data?.data.title}</h1>
        </div>
        <div className="session-actions">
          <span className="session-mode">
            {
              (
                { quick: '快速调研', standard: '标准调研', deep: '深度调研' } as Record<
                  string,
                  string
                >
              )[run?.selection?.mode ?? project.data?.data.mode ?? 'standard']
            }
          </span>
          <button
            className="outline-button session-secondary-action"
            disabled
            title="分享功能尚未开放"
          >
            <Share2 size={15} />
            分享
          </button>
          <button
            className="outline-button session-secondary-action"
            disabled
            title="报告导出将在后续切片开放"
          >
            <Download size={15} />
            导出
          </button>
          <span className={`run-status ${activeRun(run) ? 'is-running' : ''}`} role="status">
            {run ? (statuses[run.status] ?? run.status) : '尚未开始'}
          </span>
          <button className="icon-button" aria-label="刷新会话" onClick={refresh}>
            <RefreshCw size={17} />
          </button>
          <button
            className="session-report-action"
            disabled={typeof reportId !== 'string'}
            title={typeof reportId === 'string' ? '打开当前已保存的报告' : '报告由研究流程自动生成'}
            onClick={() => {
              setPanel('report');
              setReportTab('content');
              document.getElementById('session-report')?.focus();
            }}
          >
            <Sparkles size={15} />
            查看报告
          </button>
          {activeRun(run) && (
            <button
              className="outline-button"
              onClick={() => {
                cancellationKey.current = crypto.randomUUID();
                cancel.reset();
                setConfirm(true);
              }}
            >
              <Square size={14} />
              取消运行
            </button>
          )}
        </div>
      </header>
      <div className="session-mobile-tabs" role="tablist" aria-label="会话面板">
        <button
          role="tab"
          aria-selected={panel === 'conversation'}
          aria-controls="session-conversation"
          onClick={() => setPanel('conversation')}
        >
          对话
        </button>
        <button
          role="tab"
          aria-selected={panel === 'report'}
          aria-controls="session-report"
          onClick={() => setPanel('report')}
        >
          报告
        </button>
      </div>
      <div className="session-columns">
        <section
          id="session-conversation"
          aria-label="研究对话"
          className={`session-conversation ${panel === 'conversation' ? 'mobile-active' : ''}`}
        >
          <div className="conversation-scroll">
            {messages.isPending ? (
              <p role="status">正在恢复消息…</p>
            ) : messages.error ? (
              <div className="form-error" role="alert">
                {messages.error.message}
                <button className="text-button" onClick={() => void messages.refetch()}>
                  重试消息
                </button>
              </div>
            ) : messages.data?.data.length ? (
              <div className="session-messages">
                {messages.data.data.map((message) => (
                  <article key={message.id} className={`session-message message-${message.role}`}>
                    <span className="message-avatar">
                      {message.role === 'user' ? <UserRound size={20} /> : <Compass size={24} />}
                    </span>
                    <div>
                      <p>
                        {typeof message.content_json.text === 'string'
                          ? message.content_json.text
                          : '结构化研究结果已保存，请查看报告与运行状态。'}
                      </p>
                      <time dateTime={message.created_at}>
                        {new Date(message.created_at).toLocaleTimeString('zh-CN')}
                      </time>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="session-empty">
                <BookOpen size={27} />
                <h2>从你的第一个问题开始</h2>
                <p>输入研究目标，执行过程和消息会真实保存。</p>
              </div>
            )}
            <section id="execution-events" className="execution-panel" aria-label="运行事件">
              <div className="section-heading">
                <h2>
                  <Activity size={18} />
                  研究计划{events.data?.some((e) => e.type === 'plan.updated') ? '（已生成）' : ''}
                </h2>
                {sortedRuns.length > 0 && (
                  <label className="run-picker">
                    <span className="sr-only">选择运行</span>
                    <select
                      aria-label="选择运行"
                      value={runId ?? ''}
                      onChange={(event) => setChosen({ threadId: id, runId: event.target.value })}
                    >
                      {sortedRuns.map((item, index) => (
                        <option key={item.id} value={item.id}>
                          运行 {sortedRuns.length - index} · {statuses[item.status] ?? item.status}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
              {runs.error && (
                <p role="alert" className="form-error">
                  {runs.error.message}
                  <button className="text-button" onClick={() => void runs.refetch()}>
                    重试运行列表
                  </button>
                </p>
              )}
              {runQuery.error && (
                <p role="alert" className="form-error">
                  {runQuery.error.message}
                  <button className="text-button" onClick={() => void runQuery.refetch()}>
                    重试状态
                  </button>
                </p>
              )}
              {events.data && <StageTimeline events={events.data} />}
              {run?.error_code && (
                <p role="alert" className="form-error">
                  运行未完成：{run.error_code}。可保留需求再次研究，或检查服务配置后重试。
                </p>
              )}
              {events.connection && (
                <div className="connection-status" role="status">
                  {connectionNames[events.connection.status]}
                  {events.connection.error && <span> · {events.connection.error}</span>}
                  {events.connection.status === 'error' && (
                    <button className="text-button" onClick={refresh}>
                      重新连接并恢复
                    </button>
                  )}
                </div>
              )}
              {events.isPending && runId ? (
                <p role="status">正在读取持久化事件…</p>
              ) : events.error ? (
                <p role="alert" className="form-error">
                  {events.error.message}
                  <button className="text-button" onClick={() => void events.refetch()}>
                    重试事件
                  </button>
                </p>
              ) : events.data?.length ? (
                <details className="complete-run-history">
                  <summary>
                    <Activity size={14} />
                    完整执行记录<span>{events.data.length} 条事件</span>
                    <ArrowUpRight size={13} />
                  </summary>
                  <ol className="run-events">
                    {events.data.map((event) => (
                      <RunEventCard key={event.event_id} event={event} />
                    ))}
                  </ol>
                </details>
              ) : (
                <p className="muted">
                  {runId ? '等待服务器保存阶段事件；不估算完成进度。' : '尚无运行记录。'}
                </p>
              )}
            </section>
            {events.data && <RunActivity events={events.data} run={run} />}
          </div>
          {project.data ? (
            <RunComposer
              key={id}
              threadId={id}
              selection={
                run?.selection ?? {
                  mode: project.data.data.mode,
                  scenario_skill_id: project.data.data.scenario_skill_id,
                  advanced_skill_ids: [],
                  advanced_skill_selection: 'manual',
                }
              }
              running={sortedRuns.some(activeRun) || activeRun(run)}
              onCreated={(nextId) => setChosen({ threadId: id, runId: nextId })}
            />
          ) : project.error ? (
            <p role="alert" className="form-error">
              项目配置加载失败，暂不能开始新研究。
              <button className="text-button" onClick={() => void project.refetch()}>
                重试配置
              </button>
            </p>
          ) : (
            <p role="status">正在读取研究配置…</p>
          )}
        </section>
        <section
          id="session-report"
          className={`session-report ${panel === 'report' ? 'mobile-active' : ''}`}
          aria-label="研究报告预览"
          tabIndex={-1}
        >
          <div className="session-report-heading">
            <h2>
              <BookOpen size={18} />
              {typeof reportId === 'string'
                ? activeRun(run)
                  ? '报告撰写中…'
                  : '研究报告'
                : activeRun(run)
                  ? '研究进行中…'
                  : '报告预览'}
            </h2>
            <a
              className="text-button"
              href="#execution-events"
              onClick={() => setPanel('conversation')}
            >
              <span className="trace-link-note">阶段用量已汇总，详情见</span>运行记录{' '}
              <ArrowUpRight size={12} />
            </a>
          </div>
          <div className="report-tabs" role="tablist" aria-label="报告视图">
            {(
              [
                { id: 'outline', title: '大纲' },
                { id: 'content', title: '内容' },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={reportTab === tab.id}
                onClick={() => setReportTab(tab.id)}
              >
                {tab.title}
              </button>
            ))}
            <button disabled title="尚未实现基于真实数据的报告图表">
              图表
            </button>
            <button
              role="tab"
              aria-selected={reportTab === 'sources'}
              onClick={() => setReportTab('sources')}
            >
              数据来源
            </button>
          </div>
          <div className="report-scroll">
            {typeof reportId === 'string' ? (
              <SavedReport key={reportId} id={reportId} view={reportTab} />
            ) : (
              <div className="session-empty">
                <BookOpen size={32} />
                <h2>{activeRun(run) ? '正在收集与分析公开资料' : '尚无报告'}</h2>
                <p>报告由 Writer 实际保存后显示。你可以在左侧查看真实步骤、工具调用和质检记录。</p>
              </div>
            )}
          </div>
          <div className="session-report-footer">
            <span>
              <Globe size={12} />
              基于本轮可追溯来源
            </span>
            <button className="text-button" disabled title="PDF 导出将在报告中心切片开放">
              导出 PDF（待开放）
            </button>
          </div>
        </section>
      </div>
      {confirm && (
        <CancelDialog
          pending={cancel.isPending}
          error={cancel.error?.message}
          onCancel={() => cancel.mutate()}
          onClose={() => setConfirm(false)}
        />
      )}
    </main>
  );
}
