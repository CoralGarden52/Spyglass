import { create } from 'zustand';

type Mode = 'quick' | 'standard' | 'deep';
type WorkbenchState = {
  draft: string;
  mode: Mode;
  setDraft: (draft: string) => void;
  setMode: (mode: Mode) => void;
};

export const useWorkbench = create<WorkbenchState>((set) => ({
  draft: '',
  mode: 'standard',
  setDraft: (draft) => set({ draft }),
  setMode: (mode) => set({ mode }),
}));
