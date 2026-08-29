/**
 * Veyra API Schema Contracts and Typed Interfaces
 * Synchronized with Backend Pydantic Schemas.
 */

export type TrustState =
  | 'UNAVAILABLE'
  | 'HIGH_CONFIDENCE'
  | 'MODERATE_CONFIDENCE'
  | 'LOW_CONFIDENCE'
  | 'ABSTAINED';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type SupportedVariable =
  | 'temperature_2m'
  | 'surface_pressure'
  | 'wind_speed_10m'
  | 'relative_humidity_2m'
  | 'precipitation';

export interface ContributingFactor {
  factor: string;
  value: number | null;
  signal: string;
}

export interface ExplanationItem {
  primary_driver: string;
  driver_summary: string;
  top_contributing_factors: ContributingFactor[];
}

export interface PredictionRequest {
  location: string;
  issue_time?: string;
  valid_time?: string;
  variable?: string;
  model_type?: string;
  target_date?: string;
}

export interface PredictionResponse {
  location: string;
  bust_probability: number | null;
  risk_level: RiskLevel | null;
  trust_state: TrustState;
  abstain: boolean;
  reason_codes: string[];
  model_version: string | null;
  data_version: string | null;
  explanation: ExplanationItem | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ModelEvaluationMetrics {
  roc_auc: number;
  brier_score: number;
  pr_auc: number;
  expected_calibration_error: number;
  f1_score: number;
  accuracy: number;
  decision_threshold: number;
}

export interface ModelEvaluationResponse {
  model_name: string;
  model_version: string;
  evaluation_dataset: string;
  sample_count: number;
  calibration: {
    is_calibrated: boolean;
    method: string;
    decision_threshold: number;
  };
  metrics: ModelEvaluationMetrics;
  feature_importance?: Record<string, number>;
}

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
  ctx?: Record<string, unknown>;
}

export interface ApiError {
  error: string;
  message?: string;
  detail?: string | ApiErrorDetail[];
  retry_after_seconds?: number;
  request_id?: string;
  status_code?: number;
}

export type HorizonPreset = '7_DAY' | '16_DAY';

export interface HorizonPointResult {
  lead_hours: number;
  lead_days: number;
  valid_time: string;
  response: PredictionResponse | null;
  status: 'SUCCESS' | 'ABSTAINED' | 'ERROR';
  error_message?: string;
}

export interface HorizonTimelineRequest {
  location: string;
  variable?: SupportedVariable;
  issue_time?: string;
  preset?: HorizonPreset;
  custom_leads?: number[];
}

export interface HorizonTimelineResult {
  location: string;
  variable: string;
  issue_time: string;
  preset: HorizonPreset;
  points: HorizonPointResult[];
  successful_count: number;
  abstained_count: number;
  error_count: number;
}
