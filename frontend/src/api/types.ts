/**
 * TypeScript type definitions strictly matching backend/app/models.py.
 */

export interface HealthResponse {
  status: string
  app_name: string
  version: string
  timestamp_utc: string
}

export interface MetadataResponse {
  project: string
  version: string
  data_provider: string
  api_base_url: string
  date_windows: {
    decision_date_start: string
    decision_date_end: string
    delivery_date_start: string
    delivery_date_end: string
    total_decision_days: number
    total_delivery_days: number
  }
  resolution: {
    fuelhh_actuals: string
    windfor_forecasts: string
    analysis_series: string
  }
  default_cutoff: string
  timezone: string
  selection_policy: {
    description: string
    rule: string
    handling_incomplete: string
    alternative_vintage: string
  }
  units: Record<string, string>
  metrics_definitions: Record<string, string>
  provenance: Record<string, any>
}

export interface HourlyIntervalComparison {
  startTime: string
  forecast_mw: number | null
  actual_mw: number | null
  signed_error_mw: number | null
  absolute_error_mw: number | null
  publish_time: string | null
  cutoff_utc: string | null
  actual_half_hour_count: number
}

export interface VintageInfo {
  publish_time: string
  total_intervals: number
  delivery_intervals_covered: number
  coverage_ratio: number
  is_complete: boolean
  is_selected_latest: boolean
  is_latest_complete: boolean
}

export interface MetricsBlock {
  expected_intervals: number
  matched_intervals: number
  omitted_intervals: number
  coverage: number
  mae: number | null
  rmse: number | null
  bias: number | null
  wape: number | null
}

export interface DeliveryDaySummary {
  delivery_date: string
  decision_date: string
  cutoff_local: string
  cutoff_utc: string
  status: 'complete' | 'incomplete' | 'unavailable'
  selected_publish_time: string | null
  latest_complete_publish_time: string | null
  expected_intervals: number
  observed_intervals: number
  coverage: number
  mae: number | null
  rmse: number | null
  bias: number | null
  wape: number | null
}

export interface DeliveryDayDetailResponse {
  delivery_date: string
  decision_date: string
  cutoff_local: string
  cutoff_utc: string
  status: 'complete' | 'incomplete' | 'unavailable'
  selected_vintage: VintageInfo | null
  latest_complete_vintage: VintageInfo | null
  intervals: HourlyIntervalComparison[]
  missing_intervals: string[]
  metrics: MetricsBlock
}

export interface OverviewResponse {
  cutoff_local: string
  decision_window: {
    start: string
    end: string
  }
  delivery_window: {
    start: string
    end: string
  }
  total_delivery_days: number
  auditable_days: number
  overall_metrics: MetricsBlock
  daily_summaries: DeliveryDaySummary[]
}

export interface DeliveriesListResponse {
  cutoff_local: string
  total_days: number
  deliveries: DeliveryDaySummary[]
}

export interface VintagesAuditResponse {
  delivery_date: string
  decision_date: string
  cutoff_local: string
  cutoff_utc: string
  selected_latest_vintage: string | null
  latest_complete_vintage: string | null
  eligible_vintages: VintageInfo[]
}
