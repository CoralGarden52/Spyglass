import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, CircleAlert, RefreshCw, Server } from 'lucide-react';
import { fetchReadiness } from '../../services/health';

const dependencyNames = {
  postgres: 'PostgreSQL',
  redis: 'Redis',
  pgvector: 'pgvector',
  migrations: '数据库迁移',
};

export function HealthStatus() {
  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: ['system', 'readiness'],
    queryFn: fetchReadiness,
    retry: false,
  });
  const title = isPending
    ? '正在检查基础服务…'
    : error
      ? '无法连接 API'
      : data?.status === 'ready'
        ? '基础服务已就绪'
        : '基础服务需要检查';
  return (
    <section className="health-panel" aria-label="系统状态">
      <div className="section-heading">
        <div className="flex items-center gap-2">
          <Server size={19} />
          <h2>系统连接</h2>
        </div>
        <button
          type="button"
          className="text-button"
          aria-label="重新检查"
          disabled={isFetching}
          onClick={() => void refetch()}
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          重新检查
        </button>
      </div>
      <div role="status" className="health-title">
        {data?.status === 'ready' ? <CheckCircle2 size={17} /> : <CircleAlert size={17} />}
        {title}
      </div>
      {data && (
        <>
          <div className="dependency-grid">
            {Object.entries(data.dependencies).map(([key, value]) => (
              <span className={value === 'ok' ? 'dependency ok' : 'dependency failed'} key={key}>
                <span className="status-dot" />
                {dependencyNames[key as keyof typeof dependencyNames]}{' '}
                {value === 'ok' ? '已连接' : '不可用'}
              </span>
            ))}
          </div>
          <p className="provider-note">
            DeepSeek {data.providers.deepseek === 'configured' ? '已配置（未验证连通）' : '未配置'}{' '}
            · DeepSeek 搜索{' '}
            {data.providers.deepseek_search === 'configured' ? '已配置（未验证连通）' : '未配置'}
          </p>
        </>
      )}
      {error && <p className="muted">请确认 API 已启动，并检查本地端口或网络。</p>}
      <p className="muted">基础服务与供应商配置就绪后，可从工作台提交真实研究。</p>
    </section>
  );
}
