import { motion } from 'framer-motion';
import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router';
import { useIdentity } from '../features/auth/session';
import { listProjects } from '../services/research';
import {
  ArrowRight,
  BarChart3,
  ChevronRight,
  ClipboardList,
  Clock3,
  FileText,
  Globe,
  ListChecks,
  MessageSquare,
  Paperclip,
  PieChart,
  PlusCircle,
  Sparkles,
  Sun,
  Tag,
  Zap,
} from 'lucide-react';
import { WorkbenchSkills } from '../features/skills/WorkbenchSkills';
import { HealthStatus } from '../features/health/HealthStatus';
import { useWorkbench } from '../stores/workbench';
import { fetchReadiness } from '../services/health';
import { launchResearch, newLaunchAttempt, type LaunchAttempt } from '../services/launch';

const templates = [
  {
    title: '竞品深度分析',
    description: '从产品、市场、用户、商业化等维度进行系统性对比分析',
    icon: ClipboardList,
    prompt:
      '研究[产品名称 A]、[产品名称 B]的产品定位、核心功能、定价策略和公开用户评价，生成带可核验来源的竞品分析报告。',
  },
  {
    title: '功能对标分析',
    description: '围绕核心功能与体验，对竞品进行结构化对标分析',
    icon: ListChecks,
    prompt:
      '比较[产品名称 A]、[产品名称 B]的核心功能与用户体验，基于可定位来源分析差异和资料不足。',
  },
  {
    title: '市场格局分析',
    description: '分析市场规模、竞争格局与发展趋势，识别关键机会点',
    icon: PieChart,
    prompt:
      '研究[目标行业]中[产品名称 A]、[产品名称 B]的定位和竞争差异。没有可靠来源的市场规模或份额请明确标注未知。',
  },
  {
    title: '定价策略分析',
    description: '对比竞品定价体系与商业化模式，评估价格策略与市场定位',
    icon: Tag,
    prompt:
      '对比[产品名称 A]、[产品名称 B]的公开定价、计费周期、币种、套餐限制与适用用户，注明采集时间及官方来源。',
  },
];

export function Workbench() {
  const store = useWorkbench();
  const { draft, setDraft, mode, setMode } = store;
  const hasTemplateFields = /\[(产品名称[^\]]*|目标行业)\]/.test(draft);
  const attempt = useRef<LaunchAttempt | null>(null);
  const [locked, setLocked] = useState(false);
  const [savedThreadId, setSavedThreadId] = useState<string>();
  const navigate = useNavigate();
  const client = useQueryClient();
  const readiness = useQuery({
    queryKey: ['system', 'readiness'],
    queryFn: fetchReadiness,
    retry: false,
  });
  const available =
    readiness.data?.status === 'ready' &&
    readiness.data.providers.deepseek === 'configured' &&
    readiness.data.providers.deepseek_search === 'configured';
  const launch = useMutation({
    mutationFn: () => {
      const input = {
        user_message: draft.trim(),
        mode,
        scenario_skill_id: store.scenarioSkillId,
        advanced_skill_ids: store.advancedSelection === 'manual' ? store.advancedSkillIds : [],
        advanced_skill_selection: store.advancedSelection,
      };
      if (!attempt.current) attempt.current = newLaunchAttempt(input);
      else if (!locked) {
        attempt.current.input = input;
        attempt.current.threadKey = crypto.randomUUID();
        attempt.current.runKey = crypto.randomUUID();
      }
      setLocked(true);
      return launchResearch(attempt.current);
    },
    onError: () => setSavedThreadId(attempt.current?.threadId),
    onSuccess: ({ threadId, run }) => {
      client.setQueryData(['run', run.id], { schema_version: 1, data: run });
      void client.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/threads/${threadId}`);
    },
  });
  const { data: identity } = useIdentity();
  const recent = useQuery({
    queryKey: ['projects', 'recent'],
    queryFn: () => listProjects(),
    retry: false,
  });
  return (
    <motion.main
      className="workbench"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <section className="welcome">
        <h1>
          <Sun size={40} strokeWidth={1.8} />
          你好，{identity?.user.display_name}
        </h1>
        <p>你的 AI 竞品分析工作台 — 让调研、比较、验证与报告生成一体完成</p>
      </section>
      <section className="composer" aria-label="新建研究">
        <label className="sr-only" htmlFor="research-input">
          研究目标
        </label>
        <textarea
          id="research-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={launch.isPending || locked}
          maxLength={8000}
          placeholder="输入产品名称、所属行业和研究目标，对比产品能力、定价与用户口碑"
        />
        <div className="composer-toolbar">
          <div className="mode-options" role="group" aria-label="报告模式">
            {(
              [
                { id: 'quick', label: '快速调研', icon: Zap },
                { id: 'standard', label: '标准调研', icon: BarChart3 },
                { id: 'deep', label: '深度调研', icon: Clock3 },
              ] as const
            ).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={mode === id ? 'mode-button selected' : 'mode-button'}
                aria-pressed={mode === id}
                onClick={() => setMode(id)}
                disabled={launch.isPending || locked}
              >
                <Icon size={17} />
                {label}
              </button>
            ))}
          </div>
          <div className="composer-actions">
            <button className="outline-button" disabled title="竞品管理将在后续切片开放">
              <PlusCircle size={16} />
              添加竞品
            </button>
            <button
              className="icon-button"
              disabled
              title="文件上传将在后续切片开放"
              aria-label="上传文件（尚未开放）"
            >
              <Paperclip size={18} />
            </button>
            <span className="search-status">
              <Globe size={16} />
              公开来源检索
            </span>
            <button
              className="primary-button"
              disabled={!draft.trim() || hasTemplateFields || !available || launch.isPending}
              onClick={() => launch.mutate()}
              aria-describedby="research-disabled"
            >
              {launch.isPending ? '正在创建研究…' : launch.error ? '重试开始分析' : '开始分析'}{' '}
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
        <p id="research-disabled" className="composer-note">
          {hasTemplateFields
            ? '请将模板中的产品名称和行业替换为本次研究目标后，再开始分析。'
            : readiness.isPending
              ? '正在检查研究服务…'
              : !available
                ? '研究服务未就绪或 DeepSeek 模型/搜索未配置，请检查系统连接后重试。'
                : '使用公开来源与已选技能开始真实研究；未找到的事实将标记证据不足。'}
        </p>
        {launch.error && (
          <div role="alert" className="form-error">
            {launch.error.message}。已保留配置和创建记录，重试将使用同一幂等请求。
          </div>
        )}
        {launch.error && (
          <button
            className="text-button"
            onClick={() => {
              const savedThread = attempt.current?.threadId;
              if (savedThread) navigate(`/threads/${savedThread}`);
              else {
                setLocked(false);
                launch.reset();
              }
            }}
          >
            {savedThreadId ? '打开已保存会话并调整配置' : '返回编辑研究需求'}
          </button>
        )}
      </section>
      <fieldset className="workbench-skills-fieldset" disabled={launch.isPending || locked}>
        <WorkbenchSkills />
      </fieldset>
      <section className="template-section">
        <div className="section-heading">
          <div className="section-title">
            <ClipboardList size={23} />
            <h2>推荐模板</h2>
            <p>从一个清晰的问题开始，构建可溯源的分析。</p>
          </div>
        </div>
        <div className="template-grid">
          {templates.map(({ title, description, icon: Icon, prompt }) => (
            <motion.button
              whileHover={{ y: -3 }}
              key={title}
              className="template-card"
              onClick={() => {
                setDraft(prompt);
                document.querySelector<HTMLTextAreaElement>('#research-input')?.focus();
              }}
              disabled={launch.isPending || locked}
            >
              <span className="tile-icon green">
                <Icon size={26} />
              </span>
              <div>
                <h3>{title}</h3>
                <p>{description}</p>
              </div>
              <ChevronRight size={17} />
            </motion.button>
          ))}
        </div>
      </section>
      <div className="bottom-grid">
        <section className="recent-panel">
          <div className="section-heading">
            <div className="section-title">
              <Clock3 size={21} />
              <h2>最近调研</h2>
            </div>
            <span className="muted">从你的第一个问题开始</span>
          </div>
          {recent.isPending ? (
            <p role="status" className="muted">
              正在加载最近调研…
            </p>
          ) : recent.error ? (
            <div role="alert">
              <p className="muted">最近调研加载失败</p>
              <button className="text-button" onClick={() => void recent.refetch()}>
                重新加载
              </button>
            </div>
          ) : recent.data?.data.length ? (
            <div className="recent-projects">
              {recent.data.data.slice(0, 2).map((project) => (
                <Link key={project.id} to={`/research/${project.id}`} className="recent-project">
                  <FileText size={23} />
                  <div>
                    <h3>{project.title}</h3>
                    <p className="muted">
                      {new Date(project.created_at).toLocaleDateString('zh-CN')} · 已保存项目
                    </p>
                  </div>
                  <ChevronRight size={16} />
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-research">
              <span className="empty-icon">
                <MessageSquare size={26} />
              </span>
              <div>
                <h3>尚未创建调研</h3>
                <p>在“我的调研”创建项目，这里将展示最近记录。</p>
              </div>
              <Sparkles size={20} />
            </div>
          )}
        </section>
        <HealthStatus />
      </div>
      <footer className="workbench-footer">
        Spyglass · 真实来源，清晰判断 <span>个人工作空间 · 无演示业务数据</span>
      </footer>
    </motion.main>
  );
}
