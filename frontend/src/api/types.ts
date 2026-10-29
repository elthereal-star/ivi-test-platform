export type Role = 'admin' | 'lead' | 'executor' | 'viewer'
export type Priority = 'P0' | 'P1' | 'P2' | 'P3'
export type ExecStatus = 'not_run' | 'pass' | 'fail' | 'blocked' | 'skip'

export interface UserInfo {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface ModuleInfo {
  id: string
  code: string
  name: string
  sort: number
}

export interface CaseStep {
  no: number
  action: string
  expected: string
}

export interface CaseInfo {
  id: string
  code: string
  title: string
  module_id: string
  priority: Priority
  case_type: string
  precondition: string
  steps: CaseStep[]
  expected: string
  tags: string[]
  status: string
  remark: string
  updated_at?: string
}

export interface Page<T> {
  total: number
  items: T[]
}

export interface PlanStats {
  total: number
  not_run: number
  passed: number
  failed: number
  blocked: number
  skipped: number
  exec_rate: number
  pass_rate: number
  p0_failed: number
}

export interface PlanInfo {
  id: string
  code: string
  name: string
  fw_version: string
  device_model: string
  device_sn: string
  status: string
  owner_id?: string
  remark: string
  created_at: string
  stats: PlanStats
}

export interface ExecRow {
  id: string
  plan_id: string
  case_id: string
  status: ExecStatus
  source: 'manual' | 'automation'
  duration_s?: number
  actual_result: string
  error_signature: string
  cluster_key: string
  attempts: number
  executed_at?: string
  case_code: string
  case_title: string
  priority: string
  module_name: string
}

export interface ModuleStat {
  module_id: string
  module_name: string
  total: number
  executed: number
  passed: number
  failed: number
  pass_rate: number
}

export interface ClusterStat {
  cluster_key: string
  count: number
  sample: string
  case_codes: string[]
  module_names: string[]
}

export interface Dashboard {
  plan_id?: string
  plan_code: string
  fw_version: string
  stats: PlanStats
  by_module: ModuleStat[]
  by_priority: { priority: string; total: number; passed: number; failed: number; pass_rate: number }[]
  top_clusters: ClusterStat[]
  trend: { plan_code: string; fw_version: string; pass_rate: number; exec_rate: number; failed: number }[]
}

export interface CompareCase {
  case_id: string
  case_code: string
  case_title: string
  priority: string
  module_name: string
  base_status: string
  target_status: string
}

export interface CompareResult {
  base_plan: PlanInfo
  target_plan: PlanInfo
  new_fail: CompareCase[]
  fixed: CompareCase[]
  still_fail: CompareCase[]
  new_case: CompareCase[]
  removed: CompareCase[]
}

export interface StabilityMetrics {
  runtime_hours: number
  total_abnormal: number
  mtbf_hours: number | null
  mtbf_cycles: number | null
  abnormal_per_hour: number
  recovery_rate: number
  auto_recover_ratio: number
  avg_recover_s: number | null
}

export interface Incident {
  id: string
  run_id: string
  incident_type: string
  module_id?: string
  occurred_at: string
  description: string
  log_excerpt: string
  recover_s?: number
  recovered: boolean
}

export interface StabilityRun {
  id: string
  code: string
  name: string
  fw_version: string
  device_sn: string
  start_at: string
  end_at: string
  planned_hours: number
  cycles_done: number
  crash_count: number
  anr_count: number
  hang_count: number
  reboot_count: number
  auto_recover_count: number
  manual_recover_count: number
  notes: string
  metrics: StabilityMetrics
  by_module: { module_name: string; count: number }[]
  by_type: { incident_type: string; count: number }[]
  incidents: Incident[]
}

export interface AiDraft {
  id: string
  module_id?: string
  requirement: string
  count: number
  model_name: string
  fallback: boolean
  cases: Omit<CaseInfo, 'id' | 'code' | 'module_id' | 'status'>[]
  status: string
  accepted_count: number
  created_at: string
}

export interface AutomationRun {
  id: string
  plan_id: string
  script_name: string
  device_sn: string
  started_at: string
  finished_at?: string
  total: number
  passed: number
  failed: number
  skipped: number
  report_url: string
}
