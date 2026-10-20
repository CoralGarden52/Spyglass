import { afterEach, expect, test } from 'vitest';
import { useWorkbench } from './workbench';

afterEach(() => useWorkbench.getState().reset());
test('private skill choices reset at the account boundary', () => {
  const store = useWorkbench.getState();
  store.setScenario('ai_llm');
  store.setAdvanced(['market_landscape']);
  store.setAdvancedSelection('auto');
  store.setDraft('private draft');
  store.reset();
  expect(useWorkbench.getState()).toMatchObject({
    draft: '',
    scenarioSkillId: 'general_analysis',
    advancedSkillIds: [],
    advancedSelection: 'manual',
    mode: 'standard',
  });
});
