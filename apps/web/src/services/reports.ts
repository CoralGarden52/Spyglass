import type { components } from '../types/api.generated';
import { request } from './client';

export const listProjectReports = (projectId: string) =>
  request<components['schemas']['ReportList']>(
    `/research/${encodeURIComponent(projectId)}/reports`,
  );
export const getReport = (reportId: string) =>
  request<components['schemas']['ReportResponse']>(`/reports/${encodeURIComponent(reportId)}`);
export const getEvidence = (evidenceId: string) =>
  request<components['schemas']['EvidenceResponse']>(`/evidence/${encodeURIComponent(evidenceId)}`);
