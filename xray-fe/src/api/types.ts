export type Verdict = 'ok' | 'watch' | 'critical' | 'skipped'

export type MetricId =
  | 'speed_to_lead'
  | 'stagnation'
  | 'discount_leakage'
  | 'sales_cycle'
  | 'key_account_risk'
  | 'dormant'
  | 'funnel_dropoff'

export type CanonicalField =
  | 'deal_id'
  | 'client'
  | 'contact'
  | 'manager'
  | 'amount'
  | 'list_price'
  | 'discount_pct'
  | 'status'
  | 'created_at'
  | 'first_contact_at'
  | 'status_changed_at'
  | 'last_activity_at'
  | 'closed_at'
  | 'source'

export type Coverage = {
  available: MetricId[]
  skipped: MetricId[]
}

export type Mapping = Partial<Record<CanonicalField, string>>

export type UploadResponse = {
  upload_id: string
  filename: string
  columns: string[]
  sample_rows: Record<string, string>[]
  suggested_mapping: Mapping
  coverage: Coverage
  auto_computed_columns?: string[]
}

export type MappingResponse = {
  coverage: Coverage
  warnings: string[]
  auto_computed_columns?: string[]
}

export type SnapshotStatus = 'processing' | 'ready' | 'failed'

export type SnapshotCreated = {
  snapshot_id: string
  status: SnapshotStatus
}

export type SnapshotPoll = {
  snapshot_id: string
  status: SnapshotStatus
  progress: number
  error: string
}

export type Finding = {
  metric_id: MetricId
  verdict: Verdict
  value: number
  unit: string
  money_impact: string | null
  action: string
  threshold_label: string
}

export type Diagnosis = {
  scan_no?: number
  headline: string
  body: string
  findings: Finding[]
  coverage: Coverage
  period: { from: string | null; to: string | null }
  totals: { deals: number; amount: string; accepted: number; rejected: number }
  available_columns?: string[]
}

export type DiagnosisResponse = Diagnosis & {
  snapshot_id: string
}

export type SnapshotListItem = {
  snapshot_id: string
  scan_no?: number
  status: SnapshotStatus
  created_at: string
  headline?: string
  filename?: string
  source?: string
  verdict?: 'critical' | 'watch' | 'ok'
  coverage_label?: string
}

export type EvidenceDeal = {
  deal_id: string
  client: string
  amount: string
  status: string
  days_stale?: number
  manager?: string
  contact?: string
}

export type MetricResult = {
  metric_id: MetricId
  available: boolean
  missing_fields: string[]
  value: number | null
  unit: string
  verdict: Verdict
  money_impact: string | null
  threshold_label: string
  action: string
}

export type MetricDetail = {
  result: MetricResult
  evidence: EvidenceDeal[]
}
