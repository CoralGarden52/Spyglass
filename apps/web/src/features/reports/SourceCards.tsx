import { useState } from 'react';
import {
  ArrowUpRight,
  CalendarDays,
  Check,
  FileSearch,
  Globe,
  Search,
  ShieldCheck,
} from 'lucide-react';
import type { components } from '../../types/api.generated';

type Source = NonNullable<
  components['schemas']['ReportResponse']['data']['search_sources']
>[number];
type Filter = 'all' | 'valid' | 'rejected';

export function SiteIcon({ url }: { url?: string | null }) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  return (
    <span className="site-logo">
      <Globe size={20} aria-label="默认站点图标" aria-hidden={loaded} />
      {url?.startsWith('https://') && !failed ? (
        <img
          src={url}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          className={loaded ? 'is-loaded' : ''}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      ) : null}
    </span>
  );
}

function hostname(url: string) {
  try {
    return new URL(url).hostname;
  } catch {
    return '来源网站';
  }
}

export function SourceCards({
  sources,
  onEvidence,
}: {
  sources: Source[];
  onEvidence: (id: string) => void;
}) {
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const valid = sources.filter((s) => s.validity_status === 'valid').length;
  const visible = sources.filter(
    (source) =>
      (filter === 'all' || source.validity_status === filter) &&
      [source.result.title, source.result.site_name, source.result.url, source.result.snippet].some(
        (text) => text?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
      ),
  );
  return (
    <section className="sources-library" aria-label="检索来源卡片">
      <div className="sources-intro">
        <div>
          <span className="eyebrow">RESEARCH SOURCES</span>
          <h3>本轮检索来源</h3>
        </div>
        <span className="sources-total">
          {sources.length}
          <small>个候选来源</small>
        </span>
      </div>
      <div className="source-controls">
        <div className="source-filters" aria-label="来源状态筛选">
          {(
            [
              ['all', '全部', sources.length],
              ['valid', '可用于分析', valid],
              ['rejected', '已排除', sources.length - valid],
            ] as const
          ).map(([value, label, count]) => (
            <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
              {label}
              <span>{count}</span>
            </button>
          ))}
        </div>
        <label className="source-search">
          <Search size={15} />
          <span className="sr-only">搜索来源</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索标题、站点或关键词"
          />
        </label>
      </div>
      <p className="sources-policy">
        <ShieldCheck size={14} />
        来源指数结合相关性与权威度，不代表事实真实性。发布时间未知的来源会明确标注。
      </p>
      <div className="source-card-grid">
        {visible.map((source) => {
          const r = source.result;
          const accepted = source.validity_status === 'valid';
          return (
            <article
              className={`source-card ${accepted ? '' : 'source-excluded'}`}
              key={source.evidence_id}
            >
              <div className="source-card-top">
                <span className="site-icon">
                  <SiteIcon url={r.site_icon} />
                </span>
                <div className="source-site-name">
                  <strong>{r.site_name || hostname(r.url)}</strong>
                  <span>{hostname(r.url)}</span>
                </div>
                <span className={`source-state ${accepted ? 'is-valid' : ''}`}>
                  {accepted ? <Check size={11} /> : null}
                  {accepted ? '已收录' : '已排除'}
                </span>
              </div>
              <a
                className="source-card-title"
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {r.title || '未提供网页标题'}
                <ArrowUpRight size={16} />
              </a>
              <p className="source-card-snippet">
                {r.snippet || '此来源未提供短摘要。可打开证据查看已保存的信息。'}
              </p>
              <div className="source-publication">
                <CalendarDays size={13} />
                <time dateTime={r.date ?? undefined}>
                  {r.date ? new Date(r.date).toISOString().slice(0, 10) + ' · UTC' : '发布时间未知'}
                </time>
                {r.authority >= 3 && (
                  <span>
                    <ShieldCheck size={12} />
                    高权威
                  </span>
                )}
              </div>
              <div className="source-card-footer">
                <div className="source-score">
                  <span>
                    相关性{' '}
                    <b>
                      {r.rerank_score == null ? '—' : r.rerank_score.toFixed(2)}
                      <small>/3</small>
                    </b>
                  </span>
                  <span>
                    权威度{' '}
                    <b>
                      {r.authority === -1 ? '—' : r.authority}
                      <small>/4</small>
                    </b>
                  </span>
                  <span>
                    来源指数{' '}
                    <b>
                      {r.source_confidence == null ? '—' : (r.source_confidence * 100).toFixed(0)}
                      <small>/100</small>
                    </b>
                  </span>
                </div>
                <button
                  onClick={() => onEvidence(source.evidence_id)}
                  aria-label={`查看证据：${r.title}`}
                >
                  <FileSearch size={14} />
                  证据
                </button>
              </div>
            </article>
          );
        })}
      </div>
      {!visible.length && (
        <div className="source-empty">
          <Search size={26} />
          <h4>没有匹配的来源</h4>
          <p>试试其他关键词，或切换来源状态。</p>
          <button
            className="text-button"
            onClick={() => {
              setFilter('all');
              setQuery('');
            }}
          >
            重置筛选
          </button>
        </div>
      )}
      <p className="source-results-count">
        显示 {visible.length} / {sources.length} 个来源 · 相关性低于 1.5
        或缺少长摘要的结果不进入分析
      </p>
    </section>
  );
}
