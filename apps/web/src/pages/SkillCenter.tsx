import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  ArrowRight,
  Search,
  ShieldCheck,
  Shapes,
  SlidersHorizontal,
} from 'lucide-react';
import {
  getSkill,
  listSkills,
  updateSkill,
  type Skill,
  type SkillDetail,
  type ScenarioID,
} from '../services/skills';
import { SkillIcon } from '../features/skills/SkillIcon';
import { useWorkbench } from '../stores/workbench';

const kinds = { all: '全部技能', scenario: '场景技能', core: '基础分析', advanced: '增强分析' };
const status = (skill: Skill) =>
  skill.is_system_required
    ? '系统必选'
    : skill.kind === 'scenario'
      ? '主场景单选'
      : skill.enabled
        ? '已启用'
        : '已停用';

export function SkillCenter() {
  const [kind, setKind] = useState<keyof typeof kinds>('all');
  const [search, setSearch] = useState('');
  const query = useQuery({ queryKey: ['skills'], queryFn: listSkills, retry: false });
  const rows = query.data?.data ?? [];
  const filtered = rows.filter(
    (s) =>
      (kind === 'all' || s.kind === kind) &&
      `${s.name} ${s.id} ${s.description}`.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <motion.main
      className="skills-page"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="page-heading">
        <div>
          <h1>技能中心</h1>
          <p>为竞品研究配置专业能力，从场景到洞察构建完整分析。</p>
        </div>
        <button className="outline-button" disabled title="自定义技能创建尚未开放">
          创建技能（尚未开放）
        </button>
      </div>
      <div className="skill-stats">
        {(['all', 'scenario', 'core', 'advanced'] as const).map((k) => (
          <div key={k}>
            <Shapes size={21} />
            <span>{kinds[k]}</span>
            <strong>
              {query.isPending || query.error
                ? '—'
                : rows.filter((s) => k === 'all' || s.kind === k).length}
            </strong>
            <small>
              {k === 'all'
                ? '来自实际注册清单'
                : k === 'core'
                  ? '每次研究自动包含'
                  : k === 'scenario'
                    ? '每次研究选择一个'
                    : '按需组合分析'}
            </small>
          </div>
        ))}
      </div>
      <div className="skill-catalogue">
        <div className="skill-toolbar">
          <div className="skill-tabs" role="group" aria-label="技能分类">
            {(Object.keys(kinds) as (keyof typeof kinds)[]).map((k) => (
              <button
                key={k}
                className={kind === k ? 'selected' : ''}
                aria-pressed={kind === k}
                onClick={() => setKind(k)}
              >
                {kinds[k]}
              </button>
            ))}
          </div>
          <label className="skill-search">
            <Search size={17} />
            <input
              aria-label="搜索技能"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索技能名称、描述或 ID"
            />
          </label>
        </div>
        {query.isPending ? (
          <p role="status">正在加载技能…</p>
        ) : query.error ? (
          <div role="alert">
            技能加载失败{' '}
            <button className="text-button" onClick={() => void query.refetch()}>
              重试
            </button>
          </div>
        ) : !filtered.length ? (
          <div className="skill-empty">没有匹配的技能</div>
        ) : (
          <div className="skill-groups">
            {(['scenario', 'core', 'advanced'] as const)
              .filter((k) => filtered.some((s) => s.kind === k))
              .map((k) => (
                <section key={k} aria-label={kinds[k]}>
                  <div className="skill-group-heading">
                    <Shapes size={23} />
                    <h2>{kinds[k]}</h2>
                    <p>
                      {k === 'scenario'
                        ? '基于不同业务场景，提供专属分析框架与数据来源。'
                        : k === 'core'
                          ? '四项基础分析，每次研究由后端强制包含。'
                          : '扩展研究深度，在工作台手动或按清单规则组合。'}
                    </p>
                    <span>{filtered.filter((s) => s.kind === k).length} 项</span>
                  </div>
                  <div className="skill-card-grid">
                    {filtered
                      .filter((s) => s.kind === k)
                      .map((s) => (
                        <motion.article whileHover={{ y: -3 }} className="skill-card" key={s.id}>
                          <div className="skill-card-top">
                            <SkillIcon id={s.id} />
                            <span className={`skill-status ${s.enabled ? '' : 'disabled'}`}>
                              {s.is_system_required && <ShieldCheck size={13} />}{' '}
                              {s.config_status === 'migration_required' ? '配置待迁移' : status(s)}
                            </span>
                          </div>
                          <h2>
                            {s.name}
                            <small>v{s.version}</small>
                          </h2>
                          <p>{s.description}</p>
                          <code>{s.id}</code>
                          <div className="dimension-tags">
                            {s.dimensions.map((d) => (
                              <span key={d}>{d}</span>
                            ))}
                          </div>
                          <div className="skill-card-footer">
                            <span>{kinds[s.kind]}</span>
                            <Link className="text-button" to={`/skills/${s.id}`}>
                              详情与配置 <ArrowRight size={15} />
                            </Link>
                          </div>
                        </motion.article>
                      ))}
                  </div>
                </section>
              ))}
          </div>
        )}
      </div>
      <p className="skills-note">
        场景在工作台单选，四项基础分析始终必选。此处管理工作空间配置；研究执行将在后续切片接入。
      </p>
    </motion.main>
  );
}

export function SkillDetails() {
  const { id = '' } = useParams();
  const query = useQuery({ queryKey: ['skills', id], queryFn: () => getSkill(id), retry: false });
  return (
    <motion.main
      className="skills-page"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <Link className="text-button" to="/skills">
        <ArrowLeft size={16} />
        返回技能中心
      </Link>
      {query.isPending ? (
        <p role="status">正在加载技能详情…</p>
      ) : query.error ? (
        <div role="alert">
          <h1>技能无法加载</h1>
          <p>{query.error.message}</p>
          <button className="outline-button" onClick={() => void query.refetch()}>
            重试
          </button>
        </div>
      ) : (
        query.data && (
          <SkillDetailContent
            key={`${id}-${query.data.data.version}-${query.data.data.revision}-${query.data.data.config_status}`}
            skill={query.data.data}
          />
        )
      )}
    </motion.main>
  );
}

function SkillDetailContent({ skill }: { skill: SkillDetail }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const setScenario = useWorkbench((s) => s.setScenario);
  const [config, setConfig] = useState<Record<string, unknown>>(skill.config);
  const [enabled, setEnabled] = useState(skill.enabled);
  const mutation = useMutation({
    mutationFn: () =>
      updateSkill(
        skill.id,
        { config, enabled, expected_revision: skill.revision },
        crypto.randomUUID(),
      ),
    onSuccess: async (result) => {
      client.setQueryData(['skills', skill.id], result);
      await client.invalidateQueries({ queryKey: ['skills'] });
      await client.invalidateQueries({ queryKey: ['skill-plan'] });
    },
  });
  const properties = (skill.config_json_schema.properties ?? {}) as Record<
    string,
    { type?: string; title?: string; minimum?: number; maximum?: number; enum?: string[] }
  >;
  return (
    <>
      <div className="skill-detail-heading">
        <SkillIcon id={skill.id} />
        <div>
          <h1>
            {skill.name}
            <small>v{skill.version}</small>
          </h1>
          <p>{skill.description}</p>
          <code>{skill.id}</code>
        </div>
        <span className="skill-status">{status(skill)}</span>
      </div>
      <div className="skill-detail-grid">
        <section className="skill-guidance">
          <h2>技能说明</h2>
          <pre>{skill.instructions}</pre>
          <h2>权限与依赖</h2>
          <p>适用 Agent：{skill.applies_to.join('、')}</p>
          <p>工具白名单：{skill.allowed_tools.join('、') || '无'}</p>
          <p>依赖：{skill.requires.join('、') || '无'}</p>
          <p className="checksum">SHA-256：{skill.manifest_checksum}</p>
          {[
            ['输入 Schema', skill.input_json_schema],
            ['输出 Schema', skill.output_json_schema],
            ['配置 Schema', skill.config_json_schema],
          ].map(([name, schema]) => (
            <details key={String(name)}>
              <summary>{String(name)}</summary>
              <pre>{JSON.stringify(schema, null, 2)}</pre>
            </details>
          ))}
        </section>
        <section className="skill-config">
          <h2>
            <SlidersHorizontal size={19} />
            工作空间配置
          </h2>
          <p className="muted" role="status">
            配置修订 {skill.revision} · 新建运行时冻结版本与参数
          </p>
          {skill.config_status === 'migration_required' && (
            <p className="config-migration" role="alert">
              技能已从 v{skill.config_version} 更新为 v{skill.version}
              。请确认并保存以下新版本参数后使用；旧配置不兼容时，此处显示新版本默认值供确认。
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              mutation.mutate();
            }}
          >
            <label className="enable-skill">
              <input
                type="checkbox"
                aria-label="启用此技能"
                checked={enabled}
                disabled={skill.kind !== 'advanced'}
                onChange={(e) => setEnabled(e.target.checked)}
              />
              {skill.kind === 'core'
                ? '系统必选，无法关闭'
                : skill.kind === 'scenario'
                  ? '始终可用，在工作台单选'
                  : '允许在当前工作空间使用'}
            </label>
            {Object.entries(properties).map(([key, schema]) => (
              <label className="config-field" key={key}>
                <span>
                  {(
                    {
                      source_language: '来源语言',
                      max_findings: '最多分析发现',
                      evidence_quote_limit: '最多引用证据',
                      review_sample_limit: '评价样本上限',
                      minimum_sample_warning: '小样本提示阈值',
                    } as Record<string, string>
                  )[key] ?? key}
                </span>
                {schema.enum ? (
                  <select
                    aria-label={key}
                    value={String(config[key])}
                    onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
                  >
                    {schema.enum.map((v) => (
                      <option key={v} value={v}>
                        {({ auto: '自动', zh: '中文', en: '英文' } as Record<string, string>)[v] ??
                          v}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    aria-label={key}
                    type="number"
                    required
                    min={schema.minimum}
                    max={schema.maximum}
                    value={String(config[key] ?? '')}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        [key]: e.target.value === '' ? '' : Number(e.target.value),
                      })
                    }
                  />
                )}
              </label>
            ))}
            {mutation.error && <p role="alert">{mutation.error.message}</p>}
            <button className="primary-button" disabled={mutation.isPending}>
              {mutation.isPending ? '保存中…' : '保存配置'}
            </button>
          </form>
          {skill.kind === 'scenario' && (
            <button
              className="outline-button"
              onClick={() => {
                setScenario(skill.id as ScenarioID);
                navigate('/');
              }}
            >
              在工作台选择此场景
            </button>
          )}
          <p className="muted">
            配置仅对当前工作空间生效。Skill 说明与版本只读；更改清单内容需要新版本。
          </p>
        </section>
      </div>
    </>
  );
}
