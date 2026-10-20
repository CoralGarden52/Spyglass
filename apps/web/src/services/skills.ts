import type { components } from '../types/api.generated';
import { request } from './client';

export type Skill = components['schemas']['SkillView'];
export type SkillDetail = components['schemas']['SkillDetail'];
export type SkillSelection = components['schemas']['Selection'];
export type AdvancedID = NonNullable<SkillSelection['advanced_skill_ids']>[number];
export type ScenarioID = NonNullable<SkillSelection['scenario_skill_id']>;
export const listSkills = () => request<components['schemas']['SkillList']>('/skills');
export const getSkill = (id: string) =>
  request<components['schemas']['SkillResult']>(`/skills/${encodeURIComponent(id)}`);
export const updateSkill = (
  id: string,
  input: components['schemas']['ConfigUpdate'],
  key: string,
) =>
  request<components['schemas']['SkillResult']>(`/skills/${encodeURIComponent(id)}/config`, {
    method: 'PATCH',
    headers: { 'Idempotency-Key': key },
    body: JSON.stringify(input),
  });
export const resolveSkills = (input: SkillSelection) =>
  request<components['schemas']['ResolutionResult']>('/skills/resolve', {
    method: 'POST',
    body: JSON.stringify(input),
  });
