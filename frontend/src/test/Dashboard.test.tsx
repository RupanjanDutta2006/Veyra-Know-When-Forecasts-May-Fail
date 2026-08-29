import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import { ForecastForm } from '../components/ForecastForm';
import { PredictionResult } from '../components/PredictionResult';
import { AbstentionResult } from '../components/AbstentionResult';
import { ExplainabilityView } from '../components/ExplainabilityView';
import { ErrorView } from '../components/ErrorView';
import { apiClient } from '../api/client';
import { PredictionResponse } from '../api/types';

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
    expect(screen.getByRole('heading', { level: 1, name: 'Veyra' })).toBeInTheDocument();
    expect(screen.getByText('Know When Forecasts May Fail')).toBeInTheDocument();
    expect(screen.getByLabelText(/Location or Coordinates/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Estimate Bust Probability/i })).toBeInTheDocument();
  });

  it('validates required fields and shows client-side validation error on blank location', async () => {
    render(<App />);

    const locationInput = screen.getByLabelText(/Location or Coordinates/i);
    fireEvent.change(locationInput, { target: { value: '   ' } });

    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
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

    const mockResponse: PredictionResponse = {
      location: 'Kolkata',
      bust_probability: 0.142,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: {
        primary_driver: 'stable_ensemble_agreement',
        driver_summary: 'Stable forecast with high ensemble consensus.',
        top_contributing_factors: [],
      },
    };

    vi.spyOn(apiClient, 'predictForecastBust').mockResolvedValue({
      data: mockResponse,
      requestId: 'req_kolkata_001',
    });

    render(<App />);

    const locationInput = screen.getByLabelText(/Location or Coordinates/i);
    fireEvent.change(locationInput, { target: { value: 'Kolkata' } });

    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('14.2000%')).toBeInTheDocument();
    });

    expect(screen.getByText('Risk: LOW')).toBeInTheDocument();
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

  it('TEST A: clears stale prediction and explanation when a new invalid zero-lead request is submitted', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockInitialSuccess: PredictionResponse = {
      location: 'Kolkata',
      bust_probability: 0.0571,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: {
        primary_driver: 'stable_ensemble_agreement',
        driver_summary: 'Initial stable forecast.',
        top_contributing_factors: [
          { factor: 'lead_hours', value: 96.0, signal: 'MEDIUM_RANGE_HORIZON' },
        ],
      },
    };

    vi.spyOn(apiClient, 'predictForecastBust').mockResolvedValue({
      data: mockInitialSuccess,
      requestId: 'req_init_001',
    });

    render(<App />);

    // Step 1: Initial successful prediction
    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.7100%')).toBeInTheDocument();
    });
    expect(screen.getByText('Risk: LOW')).toBeInTheDocument();
    expect(screen.getByText('Initial stable forecast.')).toBeInTheDocument();

    // Step 2: User changes inputs to invalid zero lead time
    const issueInput = screen.getByLabelText(/Issue Time/i);
    const validInput = screen.getByLabelText(/Valid Target/i);
    fireEvent.change(issueInput, { target: { value: '2026-08-29T12:30' } });
    fireEvent.change(validInput, { target: { value: '2026-08-29T12:30' } });

    // Step 3: Click submit on invalid form
    fireEvent.click(submitBtn);

    // Step 4: Verification — validation error is visible, but stale results are strictly hidden
    expect(
      screen.getByText('Forecast valid time must be strictly after the forecast issue time.')
    ).toBeInTheDocument();
    expect(screen.queryByText('5.7100%')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk: LOW')).not.toBeInTheDocument();
    expect(screen.queryByText('Initial stable forecast.')).not.toBeInTheDocument();
  });

  it('TEST B: clears previous success when subsequent request results in safe abstention', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockSuccess: PredictionResponse = {
      location: 'London',
      bust_probability: 0.12,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    const mockAbstention: PredictionResponse = {
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

    vi.spyOn(apiClient, 'predictForecastBust')
      .mockResolvedValueOnce({ data: mockSuccess })
      .mockResolvedValueOnce({ data: mockAbstention });

    render(<App />);

    const locationInput = screen.getByLabelText(/Location or Coordinates/i);
    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });

    // 1st request -> Success
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('12.0000%')).toBeInTheDocument();
    });

    // 2nd request -> Atlantis (Abstention)
    fireEvent.change(locationInput, { target: { value: 'Atlantis' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Prediction Safely Abstained')).toBeInTheDocument();
    });
    expect(screen.queryByText('12.0000%')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk: LOW')).not.toBeInTheDocument();
  });

  it('TEST C: clears stale success when subsequent request fails with network error', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockSuccess: PredictionResponse = {
      location: 'Tokyo',
      bust_probability: 0.25,
      risk_level: 'MEDIUM',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    vi.spyOn(apiClient, 'predictForecastBust')
      .mockResolvedValueOnce({ data: mockSuccess })
      .mockResolvedValueOnce({
        error: { error: 'NETWORK_ERROR', message: 'Connection lost to server', status_code: 0 },
      });

    render(<App />);
    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });

    // 1st request -> Success
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('25.0000%')).toBeInTheDocument();
    });

    // 2nd request -> Network Error
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('Network Connection Failed')).toBeInTheDocument();
    });
    expect(screen.queryByText('25.0000%')).not.toBeInTheDocument();
  });

  it('TEST D: clears old error banner when a valid retry succeeds', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockSuccess: PredictionResponse = {
      location: 'Kolkata',
      bust_probability: 0.08,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    vi.spyOn(apiClient, 'predictForecastBust')
      .mockResolvedValueOnce({
        error: { error: 'RATE_LIMIT_EXCEEDED', message: 'Rate limit hit', status_code: 429 },
      })
      .mockResolvedValueOnce({ data: mockSuccess });

    render(<App />);
    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });

    // 1st attempt -> 429
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('API Rate Limit Exceeded')).toBeInTheDocument();
    });

    // 2nd attempt -> Success
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('8.0000%')).toBeInTheDocument();
    });
    expect(screen.queryByText('API Rate Limit Exceeded')).not.toBeInTheDocument();
  });

  it('TEST E: replaces result A with result B cleanly across consecutive successful requests', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: { status: 'ok', service: 'forecast-bust-sentinel', version: '0.1.0' },
    });

    const mockA: PredictionResponse = {
      location: 'London',
      bust_probability: 0.05,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    const mockB: PredictionResponse = {
      location: 'Tokyo',
      bust_probability: 0.72,
      risk_level: 'HIGH',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'prototype-gbm-v1',
      data_version: 'gefs-openmeteo-v1.0',
      explanation: null,
    };

    vi.spyOn(apiClient, 'predictForecastBust')
      .mockResolvedValueOnce({ data: mockA })
      .mockResolvedValueOnce({ data: mockB });

    render(<App />);
    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });

    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('5.0000%')).toBeInTheDocument();
    });

    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText('72.0000%')).toBeInTheDocument();
    });
    expect(screen.queryByText('5.0000%')).not.toBeInTheDocument();
    expect(screen.getByText('Risk: HIGH')).toBeInTheDocument();
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
});
