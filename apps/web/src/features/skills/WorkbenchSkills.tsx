import { useQuery } from '@tanstack/react-query';
import { Box, Check, Shapes } from 'lucide-react';
import { Link } from 'react-router';
import {
  listSkills,
  resolveSkills,
  type AdvancedID,
  type ScenarioID,
  type SkillSelection,
} from '../../services/skills';
import { useWorkbench } from '../../stores/workbench';
import { SkillIcon } from './SkillIcon';

export function WorkbenchSkills() {
  const store = useWorkbench();
  const skills = useQuery({ queryKey: ['skills'], queryFn: listSkills, retry: false });
  const selection: SkillSelection = {
    mode: store.mode,
    scenario_skill_id: store.scenarioSkillId,
    advanced_skill_ids: store.advancedSelection === 'manual' ? store.advancedSkillIds : [],
    advanced_skill_selection: store.advancedSelection,
  };
  const plan = useQuery({
    queryKey: ['skill-plan', selection, skills.dataUpdatedAt],
    queryFn: () => resolveSkills(selection),
    enabled: !!skills.data,
    retry: false,
  });
  return (
    <section className="scenario-section">
      <div className="section-heading">
        <div className="section-title">
          <Box size={23} />
          <h2>场景技能</h2>
          <p>选择一个主场景，定义研究维度与来源优先级。</p>
        </div>
        <Link className="text-button" to="/skills">
          管理技能
        </Link>
      </div>
      {skills.isPending ? (
        <p role="status">正在加载技能…</p>
      ) : skills.error ? (
        <div role="alert">
          技能加载失败{' '}
          <button className="text-button" onClick={() => void skills.refetch()}>
            重试
          </button>
        </div>
      ) : (
        <>
          <div className="scenario-grid" role="radiogroup" aria-label="主场景">
            {skills.data?.data
              .filter((s) => s.kind === 'scenario')
              .map((s) => (
                <label
                  key={s.id}
                  className={`scenario-card ${store.scenarioSkillId === s.id ? 'default-scenario' : ''}`}
                >
                  <input
                    className="skill-radio"
                    type="radio"
                    name="scenario"
                    value={s.id}
                    checked={store.scenarioSkillId === s.id}
                    onChange={() => store.setScenario(s.id as ScenarioID)}
                    aria-label={s.name}
                  />
                  <SkillIcon id={s.id} />
                  <div>
                    <h3>
                      {s.name}
                      {s.id === 'general_analysis' && <span className="default-badge">默认</span>}
                    </h3>
                    <p>{s.description}</p>
                  </div>
                </label>
              ))}
          </div>
          <div className="core-skills">
            <span className="flex items-center gap-1.5">
              <Check size={15} />
              全部任务自动包含
            </span>
            {skills.data?.data
              .filter((s) => s.kind === 'core')
              .map((s) => (
                <label key={s.id} className="core-badge">
                  <input type="checkbox" checked disabled aria-label={`${s.name}（必选）`} />
                  {s.name}
                </label>
              ))}
            <span className="core-note">基础分析不可关闭</span>
          </div>
          <div className="advanced-skills">
            <div className="section-heading">
              <div className="section-title">
                <Shapes size={19} />
                <h3>增强分析</h3>
              </div>
              <div className="mode-options" role="group" aria-label="增强技能选择方式">
                {(['manual', 'auto'] as const).map((v) => (
                  <button
                    key={v}
                    className={`mode-button ${store.advancedSelection === v ? 'selected' : ''}`}
                    aria-pressed={store.advancedSelection === v}
                    onClick={() => store.setAdvancedSelection(v)}
                  >
                    {v === 'manual' ? '手动选择' : '自动选择'}
                  </button>
                ))}
              </div>
            </div>
            <div className="advanced-options">
              {skills.data?.data
                .filter((s) => s.kind === 'advanced')
                .map((s) => (
                  <label key={s.id}>
                    <input
                      type="checkbox"
                      aria-label={s.name}
                      disabled={
                        store.advancedSelection === 'auto' ||
                        (!s.enabled && !store.advancedSkillIds.includes(s.id as AdvancedID))
                      }
                      checked={
                        store.advancedSelection === 'auto'
                          ? !!plan.data?.data.skills.some((item) => item.id === s.id)
                          : store.advancedSkillIds.includes(s.id as AdvancedID)
                      }
                      onChange={(e) =>
                        store.setAdvanced(
                          e.target.checked
                            ? [...store.advancedSkillIds, s.id as AdvancedID]
                            : store.advancedSkillIds.filter((id) => id !== s.id),
                        )
                      }
                    />
                    {s.name}
                    {!s.enabled && <small>（工作空间已停用）</small>}
                  </label>
                ))}
            </div>
            {store.advancedSelection === 'auto' && (
              <p className="muted">
                根据主场景与报告模式的技能清单规则选择增强项；已停用的技能会被排除。
              </p>
            )}
            <div className="skill-preview" aria-label="技能计划预览" aria-live="polite">
              {plan.isFetching ? (
                '正在解析技能计划…'
              ) : plan.error ? (
                <span role="alert">
                  {plan.error.message}{' '}
                  <button className="text-button" onClick={() => void plan.refetch()}>
                    重试
                  </button>
                </span>
              ) : (
                plan.data && (
                  <>
                    <strong>计划预览 · {plan.data.data.skills.length} 项技能</strong>
                    <span>
                      {plan.data.data.skills
                        .map(
                          (s) =>
                            `${skills.data?.data.find((item) => item.id === s.id)?.name} v${s.version}`,
                        )
                        .join(' · ')}
                    </span>
                    <small>仅校验配置，尚未创建运行或调用模型。</small>
                  </>
                )
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
