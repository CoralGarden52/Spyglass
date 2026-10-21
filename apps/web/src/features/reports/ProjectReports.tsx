import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  BookOpen,
  CalendarDays,
  CircleAlert,
  ExternalLink,
  Files,
  Globe,
  MessageSquareText,
  RefreshCw,
  X,
} from 'lucide-react';
import { getEvidence, getReport, listProjectReports } from '../../services/reports';
import type { components } from '../../types/api.generated';
import { SourceCards } from './SourceCards';

function SourceIdentity({ result }: { result: components['schemas']['SearchResultMetadata'] }) {
  const [failed, setFailed] = useState(false);
  const icon = result.site_icon?.startsWith('https://') ? result.site_icon : null;
  return (
    <div className="source-identity">
      <span className="source-site">
        {icon && !failed ? (
          <img
            src={icon}
            width={18}
            height={18}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setFailed(true)}
          />
        ) : (
          <Globe size={18} aria-label="默认站点图标" />
        )}
        {result.site_name ?? '站点名称未知'}
      </span>
      <a href={result.url} target="_blank" rel="noopener noreferrer" className="source-url">
        {result.url} <ExternalLink size={12} />
      </a>
    </div>
  );
}

function SearchMetadata({ result }: { result: components['schemas']['SearchResultMetadata'] }) {
  return (
    <div className="report-limitations">
      <p>
        发布时间（UTC）：
        {result.date
          ? new Date(result.date).toISOString().replace('T', ' ').replace('.000Z', ' UTC')
          : '未知'}
      </p>
      <p>
        相关性：{result.rerank_score ?? '—'} / 3 · 权威度：
        {result.authority === -1 ? '未知' : `${result.authority} / 4`} · 来源置信度：
        {result.source_confidence === null
          ? '—'
          : `${(result.source_confidence * 100).toFixed(1)} / 100`}
      </p>
      <p className="muted">
        置信度指数 = 70% × 相关性 / 3 + 30% × 权威度 / 4，不代表事实为真的概率。低于 1.5
        分的相关性或缺少 summary 时不用于报告；未知日期不推断为近期。
      </p>
    </div>
  );
}

const statusNames: Record<string, string> = {
  complete: '已完成',
  partial: '部分结果',
  needs_review: '需复核',
  insufficient_evidence: '证据不足',
  supported: '有来源支持',
  unsupported: '待验证',
};

export function ProjectReports({ projectId }: { projectId: string }) {
  const query = useQuery({
    queryKey: ['project-reports', projectId],
    queryFn: () => listProjectReports(projectId),
    retry: false,
  });
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <section className="saved-reports">
      <div className="section-heading">
        <div className="section-title">
          <BookOpen size={22} />
          <h2>已保存的研究报告</h2>
        </div>
        <button
          className="text-button"
          onClick={() => void query.refetch()}
          disabled={query.isFetching}
        >
          <RefreshCw size={15} />
          刷新报告
        </button>
      </div>
      {query.isPending ? (
        <p role="status">正在读取报告…</p>
      ) : query.error ? (
        <div role="alert">
          {query.error.message}
          <button className="text-button" onClick={() => void query.refetch()}>
            重试
          </button>
        </div>
      ) : query.data?.data.length ? (
        <>
          <div className="report-choices">
            {query.data.data.map((report) => (
              <button
                className={`outline-button ${selected === report.id ? 'selected' : ''}`}
                key={report.id}
                aria-pressed={selected === report.id}
                onClick={() => setSelected(report.id)}
              >
                {report.title} · v{report.current_version}
              </button>
            ))}
          </div>
          {selected ? (
            <SavedReport id={selected} />
          ) : (
            <p className="muted">选择一份报告，查看持久化产物、来源与返工记录。</p>
          )}
        </>
      ) : (
        <p className="muted">暂无已保存报告。开始一次研究后，这里将显示真实保存的结果。</p>
      )}
    </section>
  );
}

export function SavedReport({
  id,
  view = 'content',
}: {
  id: string;
  view?: 'content' | 'outline' | 'sources';
}) {
  const query = useQuery({ queryKey: ['report', id], queryFn: () => getReport(id), retry: false });
  const [evidence, setEvidence] = useState<string | null>(null);
  if (query.isPending) return <p role="status">正在加载报告内容…</p>;
  if (query.error)
    return (
      <div role="alert">
        {query.error.message}
        <button className="text-button" onClick={() => void query.refetch()}>
          重试
        </button>
      </div>
    );
  if (!query.data) return null;
  const report = query.data.data;
  const searchSources = report.search_sources ?? [];
  const claimCount = report.content.sections.reduce(
    (sum, section) => sum + section.claims.length,
    0,
  );
  const sampleCount = report.content.sentiment_summary.sample_count;
  return (
    <motion.article
      className="persisted-report"
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="section-heading report-document-heading">
        <h2>{report.content.title}</h2>
        <span className="small-badge">
          {statusNames[report.content.status] ?? report.content.status}
        </span>
      </div>
      <div className="report-document-meta">
        <span>
          <CalendarDays size={15} />
          {new Date(report.created_at).toLocaleDateString('zh-CN')}
        </span>
        <span>
          <Files size={15} />
          {searchSources.length} 个候选来源
        </span>
        <span>
          <BookOpen size={15} />
          {claimCount} 条结论
        </span>
        <span>
          <MessageSquareText size={15} />
          {typeof sampleCount === 'number' ? sampleCount : '—'} 个评价样本
        </span>
        <span>v{report.current_version}</span>
      </div>
      {report.content.limitations.length > 0 && (
        <details
          className={`report-caveats ${report.content.status === 'needs_review' ? 'needs-review' : ''}`}
        >
          <summary>
            <CircleAlert size={15} />
            <strong>
              {report.content.status === 'needs_review'
                ? '报告仍有待复核内容'
                : '研究范围与证据说明'}
            </strong>
            <span>查看 {report.content.limitations.length} 项说明</span>
          </summary>
          <div>
            {report.content.limitations.map((text, index) => (
              <p key={index}>{text}</p>
            ))}
          </div>
        </details>
      )}
      {view === 'outline' && (
        <ol className="report-outline">
          {report.content.sections.map((section) => (
            <li key={section.skill_id}>
              <strong>{section.heading}</strong>
              <span className="small-badge">{statusNames[section.status] ?? section.status}</span>
            </li>
          ))}
        </ol>
      )}
      {view === 'content' &&
        report.content.sections.map((section, sectionIndex) => (
          <section className="persisted-section" key={section.skill_id}>
            <div className="section-heading">
              <h3>
                <span className="report-section-number">
                  {String(sectionIndex + 1).padStart(2, '0')}
                </span>
                {section.heading}
              </h3>
              <span className="small-badge">{statusNames[section.status] ?? section.status}</span>
            </div>
            <div className="report-claim-grid">
              {section.claims.map((claim, claimIndex) => (
                <div className="report-claim" key={claim.id}>
                  <span className="claim-number">{claimIndex + 1}</span>
                  <div className="claim-body">
                    <p>{claim.statement}</p>
                    <span className="muted">{statusNames[claim.status] ?? claim.status}</span>
                    <div className="source-buttons">
                      {claim.evidence_ids.map((source, index) => (
                        <button
                          className="text-button"
                          key={source}
                          onClick={() => setEvidence(source)}
                        >
                          证据 {index + 1}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {section.limitations.length > 0 && (
              <details className="section-limitations">
                <summary>证据范围与限制（{section.limitations.length}）</summary>
                {section.limitations.map((text, index) => (
                  <p className="muted" key={index}>
                    {text}
                  </p>
                ))}
              </details>
            )}
            <details>
              <summary>查看结构化分析产物</summary>
              <pre>{JSON.stringify(section.analysis, null, 2)}</pre>
            </details>
          </section>
        ))}
      {view === 'sources' && searchSources.length > 0 && (
        <SourceCards sources={searchSources} onEvidence={setEvidence} />
      )}
      {view === 'content' && searchSources.length > 0 && (
        <details className="report-audit">
          <summary>DeepSeek 检索来源（{searchSources.length} 条）</summary>
          <SourceCards sources={searchSources} onEvidence={setEvidence} />
        </details>
      )}
      {view === 'sources' && searchSources.length === 0 && (
        <p className="muted">
          报告未附检索来源清单。可在内容中的证据引用查看可用出处；无证据结论应标记待验证。
        </p>
      )}
      {view === 'content' && (
        <>
          <details className="report-audit">
            <summary>质检与返工记录（{report.review_history.length} 次）</summary>
            {report.review_history.map((review) => (
              <section key={review.review_count}>
                <h3>
                  第 {review.review_count} 次审查 ·{' '}
                  {review.status === 'passed'
                    ? '通过'
                    : review.status === 'repair'
                      ? '定向返工'
                      : '需人工复核'}
                </h3>
                {review.issues.map((issue, index) => (
                  <p key={index}>
                    {issue.target} · {issue.type}：{issue.description}；{issue.repair_request}
                  </p>
                ))}
                <code>产物摘要 {review.before_digest}</code>
              </section>
            ))}
            {report.artifact_history.map((item) => (
              <details key={`${item.skill_id}-${item.revision}`}>
                <summary>
                  {item.skill_id} v{item.skill_version} · 产物修订 {item.revision} · {item.status}
                </summary>
                <pre>{JSON.stringify(item.payload, null, 2)}</pre>
              </details>
            ))}
          </details>
        </>
      )}
      <details className="report-audit">
        <summary>实际模型与工具调用（{report.calls.length} 次）</summary>
        {report.calls.map((call, index) => (
          <div key={index} className="audit-call">
            <strong>{call.name}</strong>
            <span>
              {call.model ?? '工具'} · {call.status} ·{' '}
              {(
                (new Date(call.ended_at).getTime() - new Date(call.started_at).getTime()) /
                1000
              ).toFixed(2)}{' '}
              秒
            </span>
            <span>
              Token：
              {typeof call.usage_json?.total_tokens === 'number'
                ? call.usage_json.total_tokens
                : '—'}
            </span>
            {call.error_code && <span>{call.error_code}</span>}
          </div>
        ))}
      </details>
      {evidence && <EvidenceDialog id={evidence} onClose={() => setEvidence(null)} />}
    </motion.article>
  );
}

function EvidenceDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const query = useQuery({
    queryKey: ['evidence', id],
    queryFn: () => getEvidence(id),
    retry: false,
  });
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);
  return (
    <div className="evidence-overlay">
      <section role="dialog" aria-modal="true" aria-label="证据来源" className="evidence-dialog">
        <div className="section-heading">
          <h2>证据来源</h2>
          <button autoFocus className="icon-button" aria-label="关闭证据" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        {query.isPending ? (
          <p role="status">正在加载证据…</p>
        ) : query.error ? (
          <p role="alert">{query.error.message}</p>
        ) : (
          query.data && (
            <>
              <h3>{query.data.data.title}</h3>
              <p className="muted">
                {['search_snippet', 'search_summary'].includes(query.data.data.origin)
                  ? '搜索摘要，需结合原网页核验'
                  : '公开网页片段'}{' '}
                · 采集于 {new Date(query.data.data.collected_at).toLocaleString('zh-CN')}
              </p>
              {query.data.data.search_result && (
                <>
                  <SourceIdentity result={query.data.data.search_result} />
                  <p>{query.data.data.search_result.snippet}</p>
                  <SearchMetadata result={query.data.data.search_result} />
                </>
              )}
              <blockquote>{query.data.data.excerpt}</blockquote>
              <p className="muted">{query.data.data.permission_note}</p>
              <a
                className="text-button"
                href={query.data.data.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                打开原始来源 <ExternalLink size={15} />
              </a>
            </>
          )
        )}
      </section>
    </div>
  );
}
