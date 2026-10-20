import type { components } from '../types/api.generated';
import { request } from './client';

export type Project = components['schemas']['ProjectView'];
export type ProjectInput = components['schemas']['ProjectInput'];
export const listProjects = (query = '', offset = 0) =>
  request<components['schemas']['ProjectList']>(
    `/research?q=${encodeURIComponent(query)}&offset=${offset}&limit=20`,
  );
export const getProject = (id: string) =>
  request<components['schemas']['ProjectResult']>(`/research/${encodeURIComponent(id)}`);
export const createProject = (input: ProjectInput, key: string) =>
  request<components['schemas']['ProjectResult']>('/research', {
    method: 'POST',
    headers: { 'Idempotency-Key': key },
    body: JSON.stringify(input),
  });
