import { createProject } from './research';
import { createRun, createThread, type RunInput } from './runs';

export type LaunchAttempt = {
  projectKey: string;
  threadKey: string;
  runKey: string;
  input: RunInput;
  projectId?: string;
  threadId?: string;
};
export function newLaunchAttempt(input: RunInput): LaunchAttempt {
  return {
    projectKey: crypto.randomUUID(),
    threadKey: crypto.randomUUID(),
    runKey: crypto.randomUUID(),
    input,
  };
}
/** Keep every acknowledged resource ID and idempotency key through a failed retry. */
export async function launchResearch(attempt: LaunchAttempt) {
  const input = attempt.input;
  if (!attempt.projectId) {
    const project = await createProject(
      {
        title: input.user_message.slice(0, 200),
        mode: input.mode,
        scenario_skill_id: input.scenario_skill_id,
      },
      attempt.projectKey,
    );
    attempt.projectId = project.data.id;
  }
  if (!attempt.threadId) {
    const thread = await createThread(
      attempt.projectId,
      input.user_message.slice(0, 200),
      attempt.threadKey,
    );
    attempt.threadId = thread.data.id;
  }
  const run = await createRun(attempt.threadId, input, attempt.runKey);
  return { threadId: attempt.threadId, run: run.data };
}
