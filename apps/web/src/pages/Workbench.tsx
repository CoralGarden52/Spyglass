import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { useIdentity } from '../features/auth/session';
import { listProjects } from '../services/research';
import {
  ArrowRight,
  BarChart3,
  Bot,
  Box,
  Check,
  ChevronRight,
  ClipboardList,
  Clock3,
  FileText,
  Globe,
  Layers,
  ListChecks,
  MessageSquare,
  Paperclip,
  PieChart,
  PlusCircle,
  ShoppingBag,
  Sparkles,
  Sun,
  Tag,
  Wallet,
  Zap,
} from 'lucide-react';
import { HealthStatus } from '../features/health/HealthStatus';
import { useWorkbench } from '../stores/workbench';

const scenarios = [
  { title: '通用分析', description: '适用于多行业的综合分析', icon: FileText, color: 'blue' },
  { title: '电商行业', description: '平台对比与运营策略分析', icon: ShoppingBag, color: 'red' },
  { title: '互联网产品', description: '产品定位与增长策略分析', icon: Layers, color: 'purple' },
  { title: '硬件与智能设备', description: '产品规格与供应链分析', icon: Box, color: 'orange' },
  { title: 'AI 与大模型', description: '模型能力与生态格局分析', icon: Bot, color: 'blue' },
  { title: '金融行业', description: '商业模式与监管环境分析', icon: Wallet, color: 'green' },
];
const templates = [
  {
    title: '竞品深度分析',
    description: '从产品、市场、用户、商业化等维度进行系统性对比分析',
    icon: ClipboardList,
    prompt:
      '研究 Cursor、Claude Code 与 Windsurf 的产品定位、核心功能、定价策略和公开用户评价，生成带可核验来源的竞品分析报告。',
  },
  {
    title: '功能对标分析',
    description: '围绕核心功能与体验，对竞品进行结构化对标分析',
    icon: ListChecks,
    prompt:
      '比较目标竞品的核心功能与用户体验。请先向我确认产品名称和需要对比的功能，再基于来源进行分析。',
  },
  {
    title: '市场格局分析',
    description: '分析市场规模、竞争格局与发展趋势，识别关键机会点',
    icon: PieChart,
    prompt:
      '研究目标行业的主要参与者、产品定位和竞争差异。没有可靠来源的市场规模或份额请明确标注未知。',
  },
  {
    title: '定价策略分析',
    description: '对比竞品定价体系与商业化模式，评估价格策略与市场定位',
    icon: Tag,
    prompt: '对比目标竞品的公开定价、计费周期、币种、套餐限制与适用用户，注明采集时间及官方来源。',
  },
];

export function Workbench() {
  const { draft, setDraft, mode, setMode } = useWorkbench();
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
          maxLength={8000}
          placeholder="想分析哪个市场、公司或竞品？例如：分析 Cursor、Claude Code、Windsurf 的产品能力、定价和用户口碑"
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
            <button className="primary-button" disabled aria-describedby="research-disabled">
              开始分析 <ArrowRight size={18} />
            </button>
          </div>
        </div>
        <p id="research-disabled" className="composer-note">
          研究执行尚未开放。当前可编辑需求、选择模式、使用模板，并在“我的调研”中创建项目。
        </p>
      </section>
      <section className="scenario-section">
        <div className="section-heading">
          <div className="section-title">
            <Box size={23} />
            <h2>场景技能</h2>
            <p>基于不同业务场景与行业领域，提供专业的分析技能。</p>
          </div>
          <span className="small-badge">技能配置尚未开放</span>
        </div>
        <div className="scenario-grid">
          {scenarios.map(({ title, description, icon: Icon, color }, index) => (
            <div key={title} className={`scenario-card ${index === 0 ? 'default-scenario' : ''}`}>
              <span className={`tile-icon ${color}`}>
                <Icon size={23} />
              </span>
              <div>
                <h3>
                  {title}
                  {index === 0 && <span className="default-badge">默认</span>}
                </h3>
                <p>{description}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="core-skills">
          <span className="flex items-center gap-1.5">
            <Check size={15} />
            全部任务自动包含
          </span>
          {['产品能力', '定价策略', '用户评价', 'SWOT 分析'].map((name) => (
            <span key={name} className="core-badge">
              {name}
            </span>
          ))}
          <span className="core-note">技能执行尚未开放</span>
        </div>
      </section>
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
