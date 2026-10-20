import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { BookOpen, ExternalLink, RefreshCw, X } from 'lucide-react';
import { getEvidence, getReport, listProjectReports } from '../../services/reports';
import type { components } from '../../types/api.generated';

function SearchMetadata({ result }: { result: components['schemas']['SearchResultMetadata'] }) {
  return (
    <div className="report-limitations">
      <p>
        {result.site_name ?? '站点未知'} · 发布时间：
        {result.date ? new Date(result.date).toLocaleString('zh-CN') : '未知'}
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
        <p className="muted">
          暂无已保存报告。前端运行入口将在下一切片开放，当前不会自动生成示例报告。
        </p>
      )}
    </section>
  );
}

function SavedReport({ id }: { id: string }) {
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
  return (
    <motion.article
      className="persisted-report"
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="section-heading">
        <h2>{report.content.title}</h2>
        <span className="small-badge">
          {statusNames[report.content.status] ?? report.content.status}
        </span>
      </div>
      <p className="muted">
        版本 {report.current_version} · {new Date(report.created_at).toLocaleString('zh-CN')}
      </p>
      <div className="report-limitations">
        {report.content.limitations.map((text, index) => (
          <p key={index}>{text}</p>
        ))}
      </div>
      {report.content.sections.map((section) => (
        <section className="persisted-section" key={section.skill_id}>
          <div className="section-heading">
            <h3>{section.heading}</h3>
            <span className="small-badge">{statusNames[section.status] ?? section.status}</span>
          </div>
          {section.claims.map((claim) => (
            <div className="report-claim" key={claim.id}>
              <p>{claim.statement}</p>
              <span className="muted">{statusNames[claim.status] ?? claim.status}</span>
              <div className="source-buttons">
                {claim.evidence_ids.map((source, index) => (
                  <button className="text-button" key={source} onClick={() => setEvidence(source)}>
                    证据 {index + 1}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {section.limitations.map((text, index) => (
            <p className="muted" key={index}>
              {text}
            </p>
          ))}
          <details>
            <summary>查看结构化分析产物</summary>
            <pre>{JSON.stringify(section.analysis, null, 2)}</pre>
          </details>
        </section>
      ))}
      {searchSources.length > 0 && (
        <details className="report-audit">
          <summary>DeepSeek 检索来源（{searchSources.length} 条）</summary>
          {searchSources.map((source) => (
            <section key={source.evidence_id}>
              <button className="text-button" onClick={() => setEvidence(source.evidence_id)}>
                {source.result.title}
              </button>
              <p>{source.result.snippet}</p>
              <span className="small-badge">
                {source.validity_status === 'valid'
                  ? '可用于分析'
                  : '已排除：相关性不足或缺少长摘要'}
              </span>
              <SearchMetadata result={source.result} />
            </section>
          ))}
        </details>
      )}
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
                <SearchMetadata result={query.data.data.search_result} />
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
