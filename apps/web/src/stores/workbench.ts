import { create } from 'zustand';
import type { AdvancedID, ScenarioID } from '../services/skills';

type Mode = 'quick' | 'standard' | 'deep';
type WorkbenchState = {
  draft: string;
  mode: Mode;
  scenarioSkillId: ScenarioID;
  advancedSkillIds: AdvancedID[];
  advancedSelection: 'manual' | 'auto';
  setScenario: (id: ScenarioID) => void;
  setAdvanced: (ids: AdvancedID[]) => void;
  setAdvancedSelection: (selection: 'manual' | 'auto') => void;
  setDraft: (draft: string) => void;
  setMode: (mode: Mode) => void;
  reset: () => void;
};

export const useWorkbench = create<WorkbenchState>((set) => ({
  draft: '',
  mode: 'standard',
  scenarioSkillId: 'general_analysis',
  advancedSkillIds: [],
  advancedSelection: 'manual',
  setScenario: (scenarioSkillId) => set({ scenarioSkillId }),
  setAdvanced: (advancedSkillIds) => set({ advancedSkillIds }),
  setAdvancedSelection: (advancedSelection) => set({ advancedSelection }),
  setDraft: (draft) => set({ draft }),
  setMode: (mode) => set({ mode }),
  reset: () =>
    set({
      draft: '',
      mode: 'standard',
      scenarioSkillId: 'general_analysis',
      advancedSkillIds: [],
      advancedSelection: 'manual',
    }),
}));
