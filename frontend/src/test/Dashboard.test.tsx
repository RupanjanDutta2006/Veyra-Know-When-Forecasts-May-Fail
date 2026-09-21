import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import { ForecastForm } from '../components/ForecastForm';
import { PredictionResult } from '../components/PredictionResult';
import { AbstentionResult } from '../components/AbstentionResult';
import { ExplainabilityView } from '../components/ExplainabilityView';
import { ErrorView } from '../components/ErrorView';
import { apiClient } from '../api/client';
import { DashboardIntelligenceResponse, PredictionResponse } from '../api/types';

const createMockDashboard = (
  location = 'Kolkata',
  prob: number | null = 0.142,
  risk: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null = 'LOW',
  abstain = false,
  reasonCodes: string[] = ['SUCCESS']
): DashboardIntelligenceResponse => ({
  location: {
    query: location,
    resolved_name: `${location}, Synoptic Station`,
    latitude: 22.57,
    longitude: 88.36,
  },
  variable: 'temperature_2m',
  mode: 'single',
  status: abstain ? 'ABSTAINED' : 'SUCCESS',
  selected_prediction: {
    location,
    bust_probability: prob,
    risk_level: risk,
    trust_state: abstain ? 'UNAVAILABLE' : 'HIGH_CONFIDENCE',
    abstain,
    reason_codes: reasonCodes,
    model_version: abstain ? null : 'v3-lightgbm-frozen',
    data_version: abstain ? null : 'gefs-reanalysis-v3',
    explanation: abstain ? null : {
      primary_driver: 'stable_ensemble_agreement',
      driver_summary: 'Stable forecast with high ensemble consensus.',
      top_contributing_factors: [],
    },
  },
  timeline: [
    {
      lead_hours: 24,
      lead_days: 1,
      valid_time: '2026-09-12T12:00:00Z',
      bust_probability: prob,
      risk_level: risk,
      trust_state: abstain ? 'UNAVAILABLE' : 'HIGH_CONFIDENCE',
      abstain,
      is_certified_horizon: true,
      reason_codes: reasonCodes,
    },
  ],
  summary: {
    available_points: abstain ? 0 : 1,
    abstained_points: abstain ? 1 : 0,
    total_points: 1,
    max_bust_probability: prob,
    max_risk_level: risk,
    max_risk_lead_hours: 24,
    mean_bust_probability: prob,
    elevated_risk_points: 0,
    first_elevated_risk_lead_hours: null,
    overall_decision_mode: abstain ? 'ABSTAIN' : 'NOMINAL_OPERATIONS',
  },
  scientific_context: {
    model_version: 'v3-lightgbm-frozen',
    model_family: 'LightGBM-V3-Isotonic',
    calibration_method: 'isotonic',
    feature_count: 50,
    probability_semantics: 'P(Forecast Bust) under calibrated threshold',
    benchmark_scope: 'Certified frozen split',
    benchmark_lead_horizon_max_hours: 240,
    operational_horizon_max_hours: 384,
    historical_benchmark: {
      dataset: 'certified_splits_v3',
      period: '2021-2024',
      test_samples: 2920,
      test_cycles: 1460,
      average_precision: 0.54,
      pr_auc_trapezoidal: 0.53,
      roc_auc: 0.812,
      brier_score: 0.082,
      bss_vs_e0: 0.18,
      bss_vs_e1b: 0.14,
      ece: 0.045,
    },
    generalization_limits: ['Convective extremes in tropical complex terrain'],
  },
});

describe('Veyra Frontend Dashboard Component Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the dashboard with product identity and form controls', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    render(<App />);

    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByText('VEYRA SENTINEL')).toBeInTheDocument();
    expect(screen.getByText(/Atmospheric Forecast Reliability Platform/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Location Name or Coordinates/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /AUDIT RELIABILITY/i })).toBeInTheDocument();
  });

  it('validates required fields and shows client-side validation error on blank location', async () => {
    render(<App />);

    const locationInput = screen.getByLabelText(/Location Name or Coordinates/i);
    fireEvent.change(locationInput, { target: { value: '   ' } });

    const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });
    expect(submitBtn).toBeDisabled();
  });

  it('renders a normal successful prediction with accurate probability formatting', () => {
    const mockPrediction: PredictionResponse = {
      location: 'London',
      bust_probability: 0.0569,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: {
        primary_driver: 'stable_ensemble_agreement',
        driver_summary: 'Forecast is stable with low ensemble dispersion.',
        top_contributing_factors: [
          { factor: 'ensemble_std', value: 0.12, signal: 'LOW_ENSEMBLE_SPREAD' },
        ],
      },
    };

    render(<PredictionResult prediction={mockPrediction} />);

    expect(screen.getByText('5.6900%')).toBeInTheDocument();
    expect(screen.getByText('Risk: LOW')).toBeInTheDocument();
    expect(screen.getByText('Trust: High Confidence')).toBeInTheDocument();
    expect(screen.getByText('prototype-gbm-v1')).toBeInTheDocument();
  });

  it('renders abstention safely without ever converting null probability to 0% or LOW risk', () => {
    const mockAbstained: PredictionResponse = {
      location: 'Atlantis',
      bust_probability: null,
      risk_level: null,
      trust_state: 'UNAVAILABLE',
      abstain: true,
      reason_codes: ['INVALID_LOCATION'],
      model_version: null,
      data_version: null,
      explanation: null,
    };

    render(<AbstentionResult prediction={mockAbstained} />);

    expect(screen.getByText('Prediction Safely Abstained')).toBeInTheDocument();
    expect(screen.getByText('Unresolvable Location / Coordinates')).toBeInTheDocument();
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk: LOW')).not.toBeInTheDocument();
  });

  it('renders physical explainability driver summary and contributing factors', () => {
    const mockExplanation = {
      primary_driver: 'rapid_inter_cycle_revision',
      driver_summary: 'High risk driven by rapid 24h run-to-run forecast revision (+2.40 unit drift).',
      top_contributing_factors: [
        { factor: 'forecast_delta_24h', value: 2.4, signal: 'HIGH_REVISION_DRIFT' },
        { factor: 'lead_hours', value: 72.0, signal: 'MEDIUM_RANGE_HORIZON' },
      ],
    };

    render(<ExplainabilityView explanation={mockExplanation} />);

    expect(screen.getByText('Physical Explainability & Risk Attribution')).toBeInTheDocument();
    expect(screen.getByText(/High risk driven by rapid 24h run-to-run/i)).toBeInTheDocument();
    expect(screen.getByText('Forecast Delta 24h')).toBeInTheDocument();
    expect(screen.getByText('High Revision Drift')).toBeInTheDocument();
    expect(screen.getByText('2.4')).toBeInTheDocument();
  });

  it('renders HTTP 429 rate limit error with Retry-After backoff notice', () => {
    const error429 = {
      error: 'RATE_LIMIT_EXCEEDED',
      message: 'Too many requests. Please retry after the specified backoff period.',
      retry_after_seconds: 45,
      request_id: 'req_test12345678',
      status_code: 429,
    };

    render(<ErrorView error={error429} />);

    expect(screen.getByText('API Rate Limit Exceeded')).toBeInTheDocument();
    expect(screen.getByText(/Please wait approximately 45 seconds/i)).toBeInTheDocument();
    expect(screen.getByText('req_test12345678')).toBeInTheDocument();
  });

  it('renders HTTP 422 input validation errors clearly', () => {
    const error422 = {
      error: 'VALIDATION_ERROR',
      message: 'Validation failed for the request payload.',
      detail: [{ loc: ['body', 'location'], msg: 'Field required' }],
      request_id: 'req_val_err_999',
      status_code: 422,
    };

    render(<ErrorView error={error422} />);

    expect(screen.getByText('Input Validation Error')).toBeInTheDocument();
    expect(screen.getByText(/body.location: Field required/i)).toBeInTheDocument();
    expect(screen.getByText('req_val_err_999')).toBeInTheDocument();
  });

  it('renders network connection errors gracefully', () => {
    const netError = {
      error: 'NETWORK_ERROR',
      message: 'Unable to connect to Veyra backend: Failed to fetch',
      status_code: 0,
    };

    render(<ErrorView error={netError} />);

    expect(screen.getByText('Network Connection Failed')).toBeInTheDocument();
    expect(screen.getByText(/Unable to connect to Veyra backend/i)).toBeInTheDocument();
  });

  it('executes full prediction lifecycle in App component', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockDashboard = createMockDashboard('Kolkata', 0.142, 'LOW');

    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({
      data: mockDashboard,
      requestId: 'req_kolkata_001',
    });

    render(<App />);

    const locationInput = screen.getByLabelText(/Location Name or Coordinates/i);
    fireEvent.change(locationInput, { target: { value: 'Kolkata' } });

    const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('14.20%')).toBeInTheDocument();
    });

    expect(screen.getAllByText('LOW')[0]).toBeInTheDocument();

    // Switch to Explainability tab to verify driver
    const explainTab = screen.getByRole('button', { name: /Explainability/i });
    fireEvent.click(explainTab);
    expect(screen.getByText('Stable forecast with high ensemble consensus.')).toBeInTheDocument();
  });

  it('supports direct geographic coordinate input in ForecastForm', async () => {
    const handleSubmit = vi.fn();
    render(<ForecastForm onSubmit={handleSubmit} isLoading={false} />);

    const locationInput = screen.getByLabelText(/Location or Coordinates/i);
    fireEvent.change(locationInput, { target: { value: '22.5726, 88.3639' } });

    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
    fireEvent.click(submitBtn);

    expect(handleSubmit).toHaveBeenCalledWith({
      location: '22.5726, 88.3639',
      variable: 'temperature_2m',
    });
  });

  it('populates location input when clicking a quick location pill', () => {
    const handleSubmit = vi.fn();
    render(<ForecastForm onSubmit={handleSubmit} isLoading={false} />);

    const tokyoPill = screen.getByRole('button', { name: 'Tokyo' });
    fireEvent.click(tokyoPill);

    const locationInput = screen.getByLabelText(/Location or Coordinates/i) as HTMLInputElement;
    expect(locationInput.value).toBe('Tokyo');
  });

  it('dismisses error banner when close button is clicked', () => {
    const handleDismiss = vi.fn();
    const mockError = {
      error: 'TEST_ERROR',
      message: 'Temporary test message',
      status_code: 500,
    };

    render(<ErrorView error={mockError} onDismiss={handleDismiss} />);
    const dismissBtn = screen.getByRole('button', { name: /Dismiss error/i });
    fireEvent.click(dismissBtn);

    expect(handleDismiss).toHaveBeenCalled();
  });

  it('renders null explanation safely without errors', () => {
    const { container } = render(<ExplainabilityView explanation={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders HIGH risk level with appropriate styling and accessible text', () => {
    const mockHighRisk: PredictionResponse = {
      location: 'Delhi',
      bust_probability: 0.684,
      risk_level: 'HIGH',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    render(<PredictionResult prediction={mockHighRisk} />);
    expect(screen.getByText('68.4000%')).toBeInTheDocument();
    expect(screen.getByText('Risk: HIGH')).toBeInTheDocument();
  });

  it('validates and rejects invalid valid_time before or equal to issue_time', async () => {
    const handleSubmit = vi.fn();
    render(<ForecastForm onSubmit={handleSubmit} isLoading={false} />);

    const issueInput = screen.getByLabelText(/Issue Time/i);
    const validInput = screen.getByLabelText(/Valid Target/i);

    // Set valid time earlier than issue time
    fireEvent.change(issueInput, { target: { value: '2026-08-29T12:00' } });
    fireEvent.change(validInput, { target: { value: '2026-08-29T10:00' } });

    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
    fireEvent.click(submitBtn);

    expect(
      screen.getByText('Forecast valid time must be strictly after the forecast issue time.')
    ).toBeInTheDocument();
    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it('validates and rejects excessive forecast horizons (>384h)', async () => {
    const handleSubmit = vi.fn();
    render(<ForecastForm onSubmit={handleSubmit} isLoading={false} />);

    const issueInput = screen.getByLabelText(/Issue Time/i);
    const validInput = screen.getByLabelText(/Valid Target/i);

    // Set lead time to 20 days (>384h)
    fireEvent.change(issueInput, { target: { value: '2026-08-01T00:00' } });
    fireEvent.change(validInput, { target: { value: '2026-08-25T00:00' } });

    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
    fireEvent.click(submitBtn);

    expect(
      screen.getByText('Forecast horizon cannot exceed 384 hours (16 days).')
    ).toBeInTheDocument();
    expect(handleSubmit).not.toHaveBeenCalled();
  });

  // =========================================================================
  // Manual Verification Bug Fix Regression Tests (TEST A - TEST F)
  // =========================================================================

  it('TEST A: clears stale prediction when user modifies target location input', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockDashboard = createMockDashboard('Kolkata', 0.0571, 'LOW');

    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({
      data: mockDashboard,
      requestId: 'req_init_001',
    });

    render(<App />);

    // Step 1: Initial successful prediction
    const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.71%')).toBeInTheDocument();
    });
    expect(screen.getAllByText('LOW')[0]).toBeInTheDocument();

    // Step 2: User modifies location to new target
    const locationInput = screen.getByLabelText(/Location Name or Coordinates/i);
    fireEvent.change(locationInput, { target: { value: 'Mumbai' } });

    // Step 3: Verification — stale results are strictly cleared immediately
    expect(screen.queryByText('5.71%')).not.toBeInTheDocument();
  });

  it('TEST B: clears previous success when subsequent request results in safe abstention', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockSuccess = createMockDashboard('London', 0.12, 'LOW');
    const mockAbstention = createMockDashboard('Atlantis', null, null, true, ['INVALID_LOCATION']);

    vi.spyOn(apiClient, 'getDashboardIntelligence')
      .mockResolvedValueOnce({ data: mockSuccess })
      .mockResolvedValueOnce({ data: mockAbstention });

    render(<App />);

    const locationInput = screen.getByLabelText(/Location Name or Coordinates/i);
    const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });

    // 1st request -> Success
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('12.00%')).toBeInTheDocument();
    });

    // 2nd request -> Atlantis (Abstention)
    fireEvent.change(locationInput, { target: { value: 'Atlantis' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Prediction Safely Abstained/i)).toBeInTheDocument();
    });
    expect(screen.queryByText('12.00%')).not.toBeInTheDocument();
    expect(screen.queryByText('0.00%')).not.toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
  });

  it('TEST C: clears stale success when subsequent request fails with network error', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockSuccess = createMockDashboard('Tokyo', 0.25, 'MEDIUM');

    vi.spyOn(apiClient, 'getDashboardIntelligence')
      .mockResolvedValueOnce({ data: mockSuccess })
      .mockResolvedValueOnce({
        error: { error: 'NETWORK_ERROR', message: 'Connection lost to server', status_code: 0 },
      });

    render(<App />);
    const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });

    // 1st request -> Success
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('25.00%')).toBeInTheDocument();
    });

    // 2nd request -> Network Error
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('Connection lost to server')).toBeInTheDocument();
    });
    expect(screen.queryByText('25.00%')).not.toBeInTheDocument();
  });

  it('TEST D: clears old error banner when a valid retry succeeds', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockSuccess = createMockDashboard('Kolkata', 0.08, 'LOW');

    vi.spyOn(apiClient, 'getDashboardIntelligence')
      .mockResolvedValueOnce({
        error: { error: 'RATE_LIMIT_EXCEEDED', message: 'Rate limit hit', status_code: 429 },
      })
      .mockResolvedValueOnce({ data: mockSuccess });

    render(<App />);
    const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });

    // 1st attempt -> 429
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('Rate limit hit')).toBeInTheDocument();
    });

    // 2nd attempt -> Success
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('8.00%')).toBeInTheDocument();
    });
    expect(screen.queryByText('Rate limit hit')).not.toBeInTheDocument();
  });

  it('TEST E: replaces result A with result B cleanly across consecutive successful requests', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockA = createMockDashboard('London', 0.05, 'LOW');
    const mockB = createMockDashboard('Tokyo', 0.72, 'HIGH');

    vi.spyOn(apiClient, 'getDashboardIntelligence')
      .mockResolvedValueOnce({ data: mockA })
      .mockResolvedValueOnce({ data: mockB });

    render(<App />);
    const locationInput = screen.getByLabelText(/Location Name or Coordinates/i);
    const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });

    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('5.00%')).toBeInTheDocument();
    });

    fireEvent.change(locationInput, { target: { value: 'Tokyo' } });
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('72.00%')).toBeInTheDocument();
    });
    expect(screen.queryByText('5.00%')).not.toBeInTheDocument();
    expect(screen.getAllByText('HIGH')[0]).toBeInTheDocument();
  });

  it('TEST F: renders exact backend 96h lead hours and medium-range signal in ExplainabilityView', () => {
    const mock96hExplanation = {
      primary_driver: 'stable_ensemble_agreement',
      driver_summary: 'Stable medium-range 96-hour forecast consensus.',
      top_contributing_factors: [
        { factor: 'lead_hours', value: 96.0, signal: 'MEDIUM_RANGE_HORIZON' },
        { factor: 'ensemble_std', value: 1.45, signal: 'LOW_ENSEMBLE_SPREAD' },
      ],
    };

    render(<ExplainabilityView explanation={mock96hExplanation} />);

    expect(screen.getByText('Lead Hours')).toBeInTheDocument();
    expect(screen.getByText('96')).toBeInTheDocument();
    expect(screen.getByText('Medium Range Horizon')).toBeInTheDocument();
  });

  it('TEST G: accurately formats bust_probability = 0.05691234 to 5.6912% without invented digits', () => {
    const mockDetailedProb: PredictionResponse = {
      location: 'Kolkata',
      bust_probability: 0.05691234,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    render(<PredictionResult prediction={mockDetailedProb} />);
    expect(screen.getByText('5.6912%')).toBeInTheDocument();
  });

  it('TEST H: accurately formats bust_probability = 0.0571 to 5.7100%', () => {
    const mockProb: PredictionResponse = {
      location: 'Tokyo',
      bust_probability: 0.0571,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    render(<PredictionResult prediction={mockProb} />);
    expect(screen.getByText('5.7100%')).toBeInTheDocument();
  });

  it('TEST I: accurately formats bust_probability = 0.1 to 10.0000%', () => {
    const mockProb: PredictionResponse = {
      location: 'Dubai',
      bust_probability: 0.1,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    render(<PredictionResult prediction={mockProb} />);
    expect(screen.getByText('10.0000%')).toBeInTheDocument();
  });

  it('TEST J: accurately formats bust_probability = 0 to 0.0000% for non-abstained response', () => {
    const mockZeroProb: PredictionResponse = {
      location: 'London',
      bust_probability: 0.0,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    render(<PredictionResult prediction={mockZeroProb} />);
    expect(screen.getByText('0.0000%')).toBeInTheDocument();
  });

  it('TEST K: verifies abstained/null probability strictly avoids displaying 0.0000% or 0%', () => {
    const mockAbstained: PredictionResponse = {
      location: 'Atlantis',
      bust_probability: null,
      risk_level: null,
      trust_state: 'UNAVAILABLE',
      abstain: true,
      reason_codes: ['INVALID_LOCATION'],
      model_version: null,
      data_version: null,
      explanation: null,
    };

    render(<AbstentionResult prediction={mockAbstained} />);
    expect(screen.getByText('Prediction Safely Abstained')).toBeInTheDocument();
    expect(screen.queryByText('0.0000%')).not.toBeInTheDocument();
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
  });

  describe('HV-002 Stale Coordinate Clearing & Geocoding Invalidation', () => {
    it('clears coordinates when user edits location away from resolved target and on failed resolution', async () => {
      vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
        data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
      });

      const mockDelhi = createMockDashboard('Delhi', 0.05, 'LOW');
      mockDelhi.location = {
        query: 'Delhi',
        resolved_name: 'Delhi, India',
        latitude: 28.6139,
        longitude: 77.209,
      };

      const mockInvalid = createMockDashboard('asdfghjkl-not-a-real-place', null, null, true, ['INVALID_LOCATION']);
      mockInvalid.location = {
        query: 'asdfghjkl-not-a-real-place',
        resolved_name: null,
        latitude: null,
        longitude: null,
      };

      vi.spyOn(apiClient, 'getDashboardIntelligence')
        .mockResolvedValueOnce({ data: mockDelhi })
        .mockResolvedValueOnce({ data: mockInvalid });

      render(<App />);

      const locationInput = screen.getByLabelText(/Location Name or Coordinates/i);
      const latInput = screen.getByLabelText(/Latitude/i) as HTMLInputElement;
      const lonInput = screen.getByLabelText(/Longitude/i) as HTMLInputElement;
      const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });

      // Step 1: Initial Delhi resolution
      fireEvent.change(locationInput, { target: { value: 'Delhi' } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText('5.00%')).toBeInTheDocument();
      });
      expect(latInput.value).toBe('28.6139');
      expect(lonInput.value).toBe('77.209');

      // Step 2: User types invalid string
      fireEvent.change(locationInput, { target: { value: 'asdfghjkl-not-a-real-place' } });

      // Coordinates must immediately be cleared/unresolved (NOT retaining Delhi)
      expect(latInput.value).toBe('');
      expect(lonInput.value).toBe('');

      // Step 3: Trigger Audit which fails resolution
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Prediction Safely Abstained/i)).toBeInTheDocument();
      });

      // Coordinates must still remain blank/unresolved
      expect(latInput.value).toBe('');
      expect(lonInput.value).toBe('');
      expect(screen.queryByText('28.6139')).not.toBeInTheDocument();
      expect(screen.queryByText('77.209')).not.toBeInTheDocument();
    });

    it('restores correct coordinates when valid location is queried after an invalid resolution failure', async () => {
      vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
        data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
      });

      const mockInvalid = createMockDashboard('invalid-city', null, null, true, ['INVALID_LOCATION']);
      mockInvalid.location = {
        query: 'invalid-city',
        resolved_name: null,
        latitude: null,
        longitude: null,
      };

      const mockKolkata = createMockDashboard('Kolkata', 0.142, 'LOW');
      mockKolkata.location = {
        query: 'Kolkata',
        resolved_name: 'Kolkata, Synoptic Station',
        latitude: 22.57,
        longitude: 88.36,
      };

      vi.spyOn(apiClient, 'getDashboardIntelligence')
        .mockResolvedValueOnce({ data: mockInvalid })
        .mockResolvedValueOnce({ data: mockKolkata });

      render(<App />);

      const locationInput = screen.getByLabelText(/Location Name or Coordinates/i);
      const latInput = screen.getByLabelText(/Latitude/i) as HTMLInputElement;
      const lonInput = screen.getByLabelText(/Longitude/i) as HTMLInputElement;
      const submitBtn = screen.getByRole('button', { name: /AUDIT RELIABILITY/i });

      // 1. Query invalid location
      fireEvent.change(locationInput, { target: { value: 'invalid-city' } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Prediction Safely Abstained/i)).toBeInTheDocument();
      });
      expect(latInput.value).toBe('');
      expect(lonInput.value).toBe('');

      // 2. Query Kolkata
      fireEvent.change(locationInput, { target: { value: 'Kolkata' } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText('14.20%')).toBeInTheDocument();
      });
      expect(latInput.value).toBe('22.57');
      expect(lonInput.value).toBe('88.36');
    });
  });
});

