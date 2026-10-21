import { useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Send } from 'lucide-react';
import { createRun, type RunInput } from '../../services/runs';
import { listSkills, type SkillSelection } from '../../services/skills';
import { fetchReadiness } from '../../services/health';

export function RunComposer({
  threadId,
  selection,
  running,
  onCreated,
}: {
  threadId: string;
  selection: SkillSelection;
  running: boolean;
  onCreated: (id: string) => void;
}) {
  const [text, setText] = useState('');
  const [edited, setEdited] = useState<SkillSelection | null>(null);
  const current = edited ?? selection;
  const key = useRef({ fingerprint: '', value: crypto.randomUUID() });
  const client = useQueryClient();
  const skills = useQuery({ queryKey: ['skills'], queryFn: listSkills, retry: false });
  const readiness = useQuery({
    queryKey: ['system', 'readiness'],
    queryFn: fetchReadiness,
    retry: false,
  });
  const available =
    readiness.data?.status === 'ready' &&
    readiness.data.providers.deepseek === 'configured' &&
    readiness.data.providers.deepseek_search === 'configured';
  const mutation = useMutation({
    mutationFn: () => {
      const input: RunInput = { ...current, user_message: text.trim() };
      const fingerprint = JSON.stringify(input);
      if (key.current.fingerprint !== fingerprint)
        key.current = { fingerprint, value: crypto.randomUUID() };
      return createRun(threadId, input, key.current.value);
    },
    onSuccess: ({ data }) => {
      client.setQueryData(['run', data.id], { schema_version: 1, data });
      void client.invalidateQueries({ queryKey: ['thread-runs', threadId] });
      void client.invalidateQueries({ queryKey: ['thread-messages', threadId] });
      setText('');
      key.current = { fingerprint: '', value: crypto.randomUUID() };
      onCreated(data.id);
    },
  });
  const disabled = running || mutation.isPending;
  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }
  return (
    <form className="session-composer" onSubmit={submit}>
      <label className="sr-only" htmlFor="thread-input">
        追加研究需求
      </label>
      <textarea
        id="thread-input"
        placeholder="提出新的研究需求或修正，生成下一次独立运行…"
        value={text}
        onChange={(event) => setText(event.target.value)}
        maxLength={8000}
        disabled={disabled}
      />
      <details>
        <summary>研究配置 · 四项核心分析自动包含</summary>
        <fieldset disabled={disabled} className="run-configuration">
          <label>
            报告模式
            <select
              value={current.mode}
              onChange={(e) =>
                setEdited({ ...current, mode: e.target.value as SkillSelection['mode'] })
              }
            >
              <option value="quick">快速调研</option>
              <option value="standard">标准调研</option>
              <option value="deep">深度调研</option>
            </select>
          </label>
          <label>
            主场景
            <select
              value={current.scenario_skill_id}
              onChange={(e) =>
                setEdited({
                  ...current,
                  scenario_skill_id: e.target.value as SkillSelection['scenario_skill_id'],
                })
              }
            >
              {skills.data?.data
                .filter((s) => s.kind === 'scenario')
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            增强选择
            <select
              value={current.advanced_skill_selection}
              onChange={(e) =>
                setEdited({
                  ...current,
                  advanced_skill_selection: e.target.value as 'manual' | 'auto',
                  advanced_skill_ids: [],
                })
              }
            >
              <option value="manual">手动选择</option>
              <option value="auto">自动选择</option>
            </select>
          </label>
          {skills.data?.data
            .filter((s) => s.kind === 'advanced')
            .map((s) => (
              <label className="advanced-run-option" key={s.id}>
                <input
                  type="checkbox"
                  disabled={current.advanced_skill_selection === 'auto' || !s.enabled}
                  checked={
                    current.advanced_skill_ids?.includes(
                      s.id as NonNullable<SkillSelection['advanced_skill_ids']>[number],
                    ) ?? false
                  }
                  onChange={(e) =>
                    setEdited({
                      ...current,
                      advanced_skill_ids: e.target.checked
                        ? [
                            ...(current.advanced_skill_ids ?? []),
                            s.id as NonNullable<SkillSelection['advanced_skill_ids']>[number],
                          ]
                        : current.advanced_skill_ids?.filter((id) => id !== s.id),
                    })
                  }
                />
                {s.name}
              </label>
            ))}
        </fieldset>
      </details>
      <div className="session-composer-actions">
        <span className="muted">
          {running
            ? '已有运行进行中，完成或取消后可提交。'
            : '新增需求创建后继 Run，保留已有报告。'}
        </span>
        <button
          className="primary-button"
          disabled={disabled || !available || !text.trim() || !skills.data}
          aria-label="提交研究需求"
        >
          <Send size={16} />
          {mutation.isPending ? '提交中…' : '开始研究'}
        </button>
      </div>
      {!available && (
        <p className="muted">
          研究服务未就绪或模型/搜索未配置。
          <button type="button" className="text-button" onClick={() => void readiness.refetch()}>
            重新检查
          </button>
        </p>
      )}
      {skills.error && (
        <p role="alert">
          技能配置读取失败。
          <button type="button" className="text-button" onClick={() => void skills.refetch()}>
            重试
          </button>
        </p>
      )}
      {mutation.error && (
        <p role="alert" className="form-error">
          {mutation.error.message}。输入与重试幂等键已保留。
        </p>
      )}
    </form>
  );
}
