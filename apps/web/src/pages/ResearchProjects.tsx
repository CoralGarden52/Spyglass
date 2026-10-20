import { useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import { FileText, FolderPlus, Search, X } from 'lucide-react';
import { createProject, getProject, listProjects } from '../services/research';
import { ApiError } from '../services/client';
import { ProjectReports } from '../features/reports/ProjectReports';

const modeLabels: Record<string, string> = {
  quick: '快速调研',
  standard: '标准调研',
  deep: '深度调研',
};
const scenarioLabels: Record<string, string> = {
  general_analysis: '通用分析',
  ecommerce: '电商行业',
  internet_product: '互联网产品',
  hardware_iot: '硬件与智能设备',
  ai_llm: 'AI 与大模型',
  finance: '金融行业',
};
const statusLabels: Record<string, string> = {
  draft: '草稿',
  running: '运行中',
  completed: '已完成',
  needs_review: '需复核',
  failed: '失败',
  archived: '已归档',
};

export function ResearchProjects() {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const creationKey = useRef(crypto.randomUUID());
  const client = useQueryClient();
  const projects = useQuery({
    queryKey: ['projects', query, offset],
    queryFn: () => listProjects(query, offset),
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: () =>
      createProject(
        { title: title.trim(), mode: 'standard', scenario_skill_id: 'general_analysis' },
        creationKey.current,
      ),
    onSuccess: () => {
      setTitle('');
      setCreating(false);
      creationKey.current = crypto.randomUUID();
      void client.invalidateQueries({ queryKey: ['projects'] });
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }
  return (
    <main className="business-page">
      <div className="page-heading">
        <div>
          <h1>我的调研</h1>
          <p>管理你的调研项目。项目已持久化，研究执行将在后续开放。</p>
        </div>
        <button className="soft-button" onClick={() => setCreating(true)}>
          <FolderPlus size={17} />
          创建项目
        </button>
      </div>
      <form
        className="project-search"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(search.trim());
          setOffset(0);
        }}
      >
        <Search size={18} />
        <input
          aria-label="搜索调研项目"
          value={search}
          maxLength={100}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="搜索调研项目"
        />
        <button className="outline-button">搜索</button>
      </form>
      {creating && (
        <section className="create-project-panel" aria-label="创建调研项目">
          <div className="section-heading">
            <h2>创建调研项目</h2>
            <button
              className="icon-button"
              aria-label="关闭创建项目"
              onClick={() => setCreating(false)}
            >
              <X size={17} />
            </button>
          </div>
          <form onSubmit={submit}>
            <label>
              项目名称
              <input
                required
                maxLength={200}
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value);
                  creationKey.current = crypto.randomUUID();
                }}
              />
            </label>
            <p className="muted">创建项目不会调用模型或启动调研。场景与分析技能将在后续接入。</p>
            {mutation.error && (
              <p role="alert" className="form-error">
                {mutation.error instanceof ApiError ? mutation.error.message : '创建失败，请重试'}
              </p>
            )}
            <button className="primary-button" disabled={mutation.isPending || !title.trim()}>
              {mutation.isPending ? '正在保存…' : '保存项目'}
            </button>
          </form>
        </section>
      )}
      {projects.isPending ? (
        <p role="status" className="route-state">
          正在加载项目…
        </p>
      ) : projects.error ? (
        <div role="alert" className="route-state">
          <p>项目加载失败</p>
          <button className="outline-button" onClick={() => void projects.refetch()}>
            重试
          </button>
        </div>
      ) : (
        <>
          <p className="project-count">共 {projects.data?.meta.total ?? 0} 个项目</p>
          <div className="project-list">
            {projects.data?.data.length ? (
              projects.data.data.map((project) => (
                <Link className="project-card" key={project.id} to={`/research/${project.id}`}>
                  <span className="tile-icon green">
                    <FileText size={24} />
                  </span>
                  <div>
                    <h2>{project.title}</h2>
                    <p>
                      {modeLabels[project.mode]} · {scenarioLabels[project.scenario_skill_id]}
                    </p>
                    <small>创建于 {new Date(project.created_at).toLocaleString('zh-CN')}</small>
                  </div>
                  <span className="small-badge">
                    {statusLabels[project.status] ?? project.status}
                  </span>
                  <span>查看详情 →</span>
                </Link>
              ))
            ) : (
              <div className="empty-research">
                <FileText size={28} />
                <div>
                  <h2>{query ? '没有找到匹配项目' : '尚未创建调研项目'}</h2>
                  <p>{query ? '试试其他关键词。' : '创建你的第一个项目，开始整理研究目标。'}</p>
                </div>
              </div>
            )}
          </div>
          {(projects.data?.meta.total ?? 0) > 20 && (
            <div className="pagination">
              <button
                className="outline-button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 20))}
              >
                上一页
              </button>
              <span>
                {offset + 1}–{Math.min(offset + 20, projects.data!.meta.total)}
              </span>
              <button
                className="outline-button"
                disabled={offset + 20 >= projects.data!.meta.total}
                onClick={() => setOffset(offset + 20)}
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}

export function ResearchDetail() {
  const { id = '' } = useParams();
  const project = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id),
    retry: false,
  });
  return (
    <main className="business-page">
      <Link className="text-button" to="/research">
        ← 返回我的调研
      </Link>
      {project.isPending ? (
        <p role="status" className="route-state">
          正在加载项目…
        </p>
      ) : project.error ? (
        <section className="route-state" role="alert">
          <h1>
            {project.error instanceof ApiError && project.error.status === 404
              ? '项目不存在或无权访问'
              : '项目加载失败'}
          </h1>
          <button className="outline-button" onClick={() => void project.refetch()}>
            重试
          </button>
        </section>
      ) : (
        <>
          <div className="page-heading">
            <h1>{project.data?.data.title}</h1>
            <span className="small-badge">
              {statusLabels[project.data?.data.status ?? ''] ?? '待确认'}
            </span>
          </div>
          <section className="account-panel">
            <h2>项目已保存</h2>
            <p className="muted">刷新后仍可读取项目及已保存报告。前端运行入口将在下一切片接入。</p>
            <button className="primary-button" disabled title="研究执行尚未开放">
              开始分析（尚未开放）
            </button>
          </section>
          <ProjectReports projectId={id} />
        </>
      )}
    </main>
  );
}
