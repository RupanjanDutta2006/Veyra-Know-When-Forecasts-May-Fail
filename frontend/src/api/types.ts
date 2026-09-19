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
  calibration_status?: string | null;
  confidence_index?: number | null;
  uncertainty_pct?: number | null;
  ood_score?: number | null;
  stability_index?: number | null;
  structural_overconfidence?: boolean | null;
  failure_fingerprint?: Record<string, any> | null;
  dominant_risk_drivers?: string[] | null;
  decision_mode?: string | null;
  decision_guidance?: string | null;
  within_trust_horizon?: boolean | null;
  operational_trust_horizon_hours?: number | null;
  lead_hours?: number | null;
  valid_time?: string | null;
  issue_time?: string | null;
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
  model_type?: string;
  data_version?: string;
  evaluation_dataset?: string;
  sample_count?: number;
  calibration?: {
    is_calibrated: boolean;
    method?: string;
    decision_threshold?: number;
  };
  metrics?: ModelEvaluationMetrics;
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

export type HorizonPreset = '7_DAY' | '10_DAY' | '16_DAY';

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

export interface V3EvaluationMetrics {
  average_precision: number;
  pr_auc_trapezoidal: number;
  roc_auc: number;
  brier_score: number;
  bss_vs_e0: number;
  bss_vs_e1b: number;
  ece: number;
}

export interface V3ModelEvaluationResponse {
  model_name: string;
  model_version: string;
  model_family: string;
  feature_count: number;
  calibration_method: string;
  evaluation_dataset: string;
  evaluation_split?: string;
  evaluation_period: string;
  test_samples: number;
  test_cycles: number;
  benchmark_scope: string;
  evaluation_status: string;
  metrics: V3EvaluationMetrics;
  provenance: Record<string, any>;
  generalization_limits: string[];
}

export type DashboardMode = 'single' | 'standard_7d' | 'full_16d';
export type DashboardStatus = 'SUCCESS' | 'PARTIAL' | 'ABSTAINED';

export interface DashboardLocationContext {
  query: string;
  resolved_name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  region_id?: string | null;
}

export interface DashboardTimelinePoint {
  lead_hours: number;
  lead_days: number;
  valid_time: string;
  bust_probability: number | null;
  risk_level: RiskLevel | null;
  trust_state: TrustState;
  abstain: boolean;
  reason_codes: string[];
  calibration_status?: string | null;
  decision_mode?: string | null;
  within_trust_horizon?: boolean | null;
  operational_trust_horizon_hours?: number | null;
  is_certified_horizon: boolean;
}

export interface DashboardSummary {
  available_points: number;
  abstained_points: number;
  total_points: number;
  max_bust_probability: number | null;
  max_risk_level: RiskLevel | null;
  max_risk_lead_hours: number | null;
  mean_bust_probability: number | null;
  elevated_risk_points: number;
  first_elevated_risk_lead_hours: number | null;
  overall_decision_mode: string;
}

export interface DashboardScientificContext {
  model_version: string;
  model_family: string;
  calibration_method: string;
  feature_count: number;
  probability_semantics: string;
  benchmark_scope: string;
  benchmark_lead_horizon_max_hours: number;
  operational_horizon_max_hours: number;
  historical_benchmark: V3EvaluationMetrics & {
    dataset: string;
    period: string;
    test_samples: number;
    test_cycles: number;
  };
  generalization_limits: string[];
}

export interface DashboardRequest {
  location: string;
  variable?: string;
  mode?: DashboardMode;
  issue_time?: string | null;
}

export interface DashboardIntelligenceResponse {
  status: DashboardStatus;
  location: DashboardLocationContext;
  variable: string;
  issue_time?: string | null;
  mode: DashboardMode;
  selected_prediction: PredictionResponse;
  timeline: DashboardTimelinePoint[];
  summary: DashboardSummary;
  scientific_context: DashboardScientificContext;
  request_id?: string | null;
}

export interface MultiLocationPredictionRequest {
  locations: string[];
  variable?: string;
  target_date?: string;
  issue_time?: string;
  valid_time?: string;
  model_type?: string;
}

export interface MultiLocationPredictionItemResult {
  input_location: string;
  is_success: boolean;
  response: PredictionResponse;
}

export interface MultiLocationPredictionResult {
  batch_size: number;
  successful_predictions: number;
  abstained_predictions: number;
  results: MultiLocationPredictionItemResult[];
  metadata?: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Day 27 Spatial Reliability Intelligence Contracts
// ---------------------------------------------------------------------------

export interface SpatialReliabilityRequest {
  locations: string[];
  variable?: string;
  lead_hours?: number;
  issue_time?: string | null;
}

export interface SpatialReliabilityPoint {
  location: string;
  resolved_name?: string | null;
  latitude: number | null;
  longitude: number | null;
  region_id?: string | null;
  variable: string;
  lead_hours: number;
  lead_days: number;
  issue_time?: string | null;
  valid_time?: string | null;
  bust_probability: number | null;
  risk_level: RiskLevel | null;
  trust_state: TrustState;
  abstain: boolean;
  reason_codes: string[];
  calibration_status?: string | null;
  model_version?: string | null;
  data_version?: string | null;
  is_certified_horizon: boolean;
  scientific_scope: string;
  confidence_index?: number | null;
  uncertainty_pct?: number | null;
  ood_score?: number | null;
  stability_index?: number | null;
  dominant_risk_drivers?: string[] | null;
  decision_mode?: string | null;
  decision_guidance?: string | null;
  ensemble_spread?: number | null;
  ensemble_range?: number | null;
  ensemble_iqr?: number | null;
  ensemble_cv?: number | null;
  spread_unit?: string | null;
  member_count?: number | null;
}

export interface SpatialReliabilitySummary {
  total_locations: number;
  available_locations: number;
  abstained_locations: number;
  max_bust_probability: number | null;
  max_risk_level: RiskLevel | null;
  max_risk_location: string | null;
  mean_bust_probability: number | null;
  elevated_risk_locations: number;
  low_risk_locations?: number;
  medium_risk_locations?: number;
  high_risk_locations?: number;
  critical_risk_locations?: number;
}

export interface SpatialReliabilityResponse {
  status: DashboardStatus;
  variable: string;
  lead_hours: number;
  lead_days: number;
  issue_time?: string | null;
  is_certified_horizon: boolean;
  scientific_scope: string;
  points: SpatialReliabilityPoint[];
  summary: SpatialReliabilitySummary;
  request_id?: string | null;
}

// ---------------------------------------------------------------------------
// Day 29 Forecast Disagreement Intelligence Contracts
// ---------------------------------------------------------------------------

export type DisagreementStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'ABSTAINED';

export interface DisagreementDiagnostics {
  ensemble_spread: number | null;
  ensemble_std: number | null;
  ensemble_range: number | null;
  ensemble_iqr: number | null;
  ensemble_cv: number | null;
  spread_to_iqr_ratio: number | null;
  ensemble_mean: number | null;
  ensemble_min: number | null;
  ensemble_max: number | null;
}

export interface DisagreementUnits {
  spread: string;
  range: string;
  iqr: string;
  mean: string;
  cv: string;
  spread_to_iqr_ratio: string;
  ensemble_spread?: string;
  ensemble_range?: string;
  ensemble_iqr?: string;
  ensemble_mean?: string;
  ensemble_cv?: string;
}

export interface ForecastDisagreementRequest {
  location: string;
  variable?: string;
  lead_hours?: number;
  issue_time?: string | null;
  valid_time?: string | null;
  target_date?: string | null;
}

export interface ForecastDisagreementResponse {
  status: DisagreementStatus;
  location: string;
  resolved_name?: string | null;
  latitude: number | null;
  longitude: number | null;
  variable: string;
  lead_hours: number;
  lead_days: number;
  issue_time?: string | null;
  valid_time?: string | null;
  diagnostics: DisagreementDiagnostics | null;
  units: DisagreementUnits | null;
  member_count: number | null;
  has_full_ensemble: boolean | null;
  bust_probability: number | null;
  risk_level: RiskLevel | null;
  trust_state: TrustState;
  calibration_status?: string | null;
  scientific_scope: string;
  is_certified_horizon: boolean;
  abstain: boolean;
  reason_codes: string[];
  request_id: string;
}

