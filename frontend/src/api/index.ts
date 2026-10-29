import { http } from './client'
import type {
  AiDraft,
  AutomationRun,
  CaseInfo,
  CompareResult,
  Dashboard,
  ExecRow,
  ModuleInfo,
  Page,
  PlanInfo,
  StabilityRun,
  UserInfo,
} from './types'

export const authApi = {
  login: (email: string, password: string) =>
    http.post<{ access_token: string; user: UserInfo }>('/auth/login', { email, password }).then((r) => r.data),
  me: () => http.get<UserInfo>('/auth/me').then((r) => r.data),
}

export const userApi = {
  list: () => http.get<Page<UserInfo>>('/users').then((r) => r.data.items),
  create: (payload: { email: string; full_name: string; password: string; role: string }) =>
    http.post<UserInfo>('/users', payload).then((r) => r.data),
  update: (id: string, payload: Record<string, unknown>) =>
    http.patch<UserInfo>(`/users/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/users/${id}`).then((r) => r.data),
}

export const metaApi = {
  modules: () => http.get<ModuleInfo[]>('/modules').then((r) => r.data),
  createModule: (payload: { code: string; name: string; sort?: number }) =>
    http.post<ModuleInfo>('/modules', payload).then((r) => r.data),
}

export const caseApi = {
  list: (params: Record<string, unknown>) => http.get<Page<CaseInfo>>('/cases', { params }).then((r) => r.data),
  detail: (id: string) => http.get<CaseInfo>(`/cases/${id}`).then((r) => r.data),
  create: (payload: Partial<CaseInfo>) => http.post<CaseInfo>('/cases', payload).then((r) => r.data),
  update: (id: string, payload: Partial<CaseInfo>) =>
    http.patch<CaseInfo>(`/cases/${id}`, payload).then((r) => r.data),
  deprecate: (id: string) => http.delete<CaseInfo>(`/cases/${id}`).then((r) => r.data),
  import: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http
      .post<{ created: number; updated: number; skipped: number; errors: { row: number; reason: string }[] }>(
        '/cases/import',
        form,
      )
      .then((r) => r.data)
  },
  templateUrl: '/api/v1/cases/template',
  exportUrl: '/api/v1/cases/export',
}

export const planApi = {
  list: (params: Record<string, unknown> = {}) => http.get<Page<PlanInfo>>('/plans', { params }).then((r) => r.data),
  detail: (id: string) => http.get<PlanInfo>(`/plans/${id}`).then((r) => r.data),
  create: (payload: Record<string, unknown>, allCases = false) =>
    http.post<PlanInfo>('/plans', payload, { params: { all_cases: allCases } }).then((r) => r.data),
  update: (id: string, payload: Record<string, unknown>) =>
    http.patch<PlanInfo>(`/plans/${id}`, payload).then((r) => r.data),
  addCases: (id: string, caseIds: string[]) =>
    http.post<PlanInfo>(`/plans/${id}/add-cases`, caseIds).then((r) => r.data),
  executions: (id: string, params: Record<string, unknown> = {}) =>
    http.get<ExecRow[]>(`/plans/${id}/executions`, { params }).then((r) => r.data),
  submitExecution: (id: string, payload: Record<string, unknown>) =>
    http.put<ExecRow>(`/plans/${id}/executions`, payload).then((r) => r.data),
  assign: (planId: string, caseId: string, assigneeId: string) =>
    http.patch(`/plans/${planId}/executions/${caseId}/assign`, null, { params: { assignee_id: assigneeId } }),
  exportUrl: (id: string) => `/api/v1/plans/${id}/export`,
}

export const reportApi = {
  dashboard: (planId?: string) =>
    http.get<Dashboard>('/reports/dashboard', { params: planId ? { plan_id: planId } : {} }).then((r) => r.data),
  compare: (baseId: string, targetId: string) =>
    http
      .get<CompareResult>('/reports/compare', { params: { base_plan_id: baseId, target_plan_id: targetId } })
      .then((r) => r.data),
}

export const stabilityApi = {
  list: () => http.get<StabilityRun[]>('/stability/runs').then((r) => r.data),
  create: (payload: Record<string, unknown>) => http.post<StabilityRun>('/stability/runs', payload).then((r) => r.data),
  addIncident: (runId: string, payload: Record<string, unknown>) =>
    http.post(`/stability/runs/${runId}/incidents`, payload).then((r) => r.data),
}

export const aiApi = {
  generate: (payload: { module_id: string; requirement: string; count: number; priority: string }) =>
    http.post<AiDraft>('/ai/generate', payload).then((r) => r.data),
  drafts: () => http.get<AiDraft[]>('/ai/drafts').then((r) => r.data),
  accept: (id: string, indices: number[]) =>
    http.post<{ created: number; case_codes: string[] }>(`/ai/drafts/${id}/accept`, { indices }).then((r) => r.data),
  reject: (id: string) => http.post<AiDraft>(`/ai/drafts/${id}/reject`).then((r) => r.data),
}

export const automationApi = {
  runs: (planId?: string) =>
    http.get<AutomationRun[]>('/automation/runs', { params: planId ? { plan_id: planId } : {} }).then((r) => r.data),
}
