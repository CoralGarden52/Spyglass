import type { components } from '../types/api.generated';
import { ApiError, request } from './client';

export type Identity = components['schemas']['Identity'];
export type LoginInput = components['schemas']['LoginInput'];
export type RegisterInput = components['schemas']['RegisterInput'];

export async function getIdentity(): Promise<Identity | null> {
  try {
    return await request<Identity>('/users/me');
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export const login = (input: LoginInput) =>
  request<Identity>('/auth/login', { method: 'POST', body: JSON.stringify(input) });
export const register = (input: RegisterInput) =>
  request<Identity>('/auth/register', { method: 'POST', body: JSON.stringify(input) });
export const logout = () => request<void>('/auth/logout', { method: 'POST' });
