import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ForecastRevisionPanel } from '../components/ForecastRevisionPanel';
import { apiClient } from '../api/client';
import { ForecastRevisionResponse } from '../api/types';

const createMockRevisionResponse = (
  overrides?: Partial<ForecastRevisionResponse>
): ForecastRevisionResponse => ({
  status: 'AVAILABLE',
  location: 'Kolkata',
  resolved_name: 'Kolkata, WB, India',
  latitude: 22.57,
  longitude: 88.36,
  variable: 'temperature_2m',
  lead_hours: 24,
  lead_days: 1.0,
  current_issue_time: '2026-09-19T06:00:00Z',
  previous_issue_time: '2026-09-19T00:00:00Z',
  valid_time: '2026-09-20T06:00:00Z',
  trajectory: {
    current_value: 29.5,
    previous_value: 28.1,
    revision_delta: 1.4,
    absolute_revision: 1.4,
    direction: 'INCREASED',
  },
  ensemble_revision: {
    current_mean: 29.4,
    previous_mean: 28.0,
    mean_delta: 1.4,
    current_spread: 1.4,
    previous_spread: 1.1,
    spread_delta: 0.3,
  },
  trajectory_points: [
    {
      issue_time: '2026-09-19T00:00:00Z',
      valid_time: '2026-09-20T06:00:00Z',
      lead_hours: 30,
      forecast_value: 28.1,
      ensemble_mean: 28.0,
      ensemble_spread: 1.1,
    },
    {
      issue_time: '2026-09-19T06:00:00Z',
      valid_time: '2026-09-20T06:00:00Z',
      lead_hours: 24,
      forecast_value: 29.5,
      ensemble_mean: 29.4,
      ensemble_spread: 1.4,
    },
  ],
  current_value: 29.5,
  previous_value: 28.1,
  revision_delta: 1.4,
  units: {
    value: '°C',
    revision_delta: '°C',
    absolute_revision: '°C',
    ensemble_mean: '°C',
    ensemble_spread: '°C',
  },
  bust_probability: 0.165,
  previous_bust_probability: null,
  bust_probability_delta: null,
  risk_level: 'LOW',
  trust_state: 'HIGH_CONFIDENCE',
  calibration_status: 'CALIBRATED',
  scientific_scope: 'WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE',
  is_certified_horizon: true,
  history_is_durable: true,
  history_source: 'NOAA_GEFS_ARCHIVE',
  abstain: false,
  reason_codes: [],
  request_id: 'rev-test-req-001',
  ...overrides,
});

describe('ForecastRevisionPanel Component (Day 30)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the header with Day 30 badge and initial loading', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse(),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" />);

    expect(screen.getByText(/FORECAST REVISION \/ TRAJECTORY INTELLIGENCE/i)).toBeInTheDocument();
    expect(screen.getByText(/DAY 30/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/RUN-TO-RUN REVISION/i)).toBeInTheDocument();
    });
  });

  it('renders previous, current values, revision delta, direction, and units', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse({
        trajectory: {
          current_value: 29.5,
          previous_value: 28.1,
          revision_delta: 1.4,
          absolute_revision: 1.4,
          direction: 'INCREASED',
        },
      }),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/RUN-TO-RUN REVISION/i)).toBeInTheDocument();
    });

    expect(screen.getAllByText('28.1 °C').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('29.5 °C').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('+1.4 °C')).toBeInTheDocument();
    expect(screen.getAllByText('1.4 °C').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('INCREASED')).toBeInTheDocument();
  });

  it('strictly separates calibrated P(BUST) from revision diagnostics', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse({
        bust_probability: 0.165,
        risk_level: 'LOW',
      }),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/CALIBRATED FAILURE RISK/i)).toBeInTheDocument();
    });

    expect(screen.getByText('16.5%')).toBeInTheDocument();
    expect(screen.getByText('P(BUST)')).toBeInTheDocument();
    expect(screen.getByText(/Revision Delta ≠ Ensemble Spread ≠ P\(BUST\)/i)).toBeInTheDocument();
  });

  it('renders truthful unavailable state when prior issue cycle data is missing without converting to 0.0', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse({
        status: 'INSUFFICIENT_HISTORY',
        trajectory: null,
        ensemble_revision: null,
        trajectory_points: [],
        current_value: null,
        previous_value: null,
        revision_delta: null,
        previous_bust_probability: null,
        bust_probability_delta: null,
        history_is_durable: false,
        history_source: null,
      }),
    });

    render(<ForecastRevisionPanel initialLocation="Bengaluru" />);

    await waitFor(() => {
      expect(screen.getByText(/INSUFFICIENT COMPARABLE ISSUE-CYCLE HISTORY/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/missing revision evidence remains null and is never converted to fake 0.0/i)).toBeInTheDocument();
    expect(screen.getByText(/No previous run, revision delta, or trajectory is manufactured/i)).toBeInTheDocument();
    expect(screen.queryByText('+0.0 °C')).not.toBeInTheDocument();
    expect(screen.queryByText('0.0 °C')).not.toBeInTheDocument();
  });

  it('renders safety abstention state for invalid locations without fake values', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse({
        status: 'ABSTAINED',
        location: 'Atlantis',
        resolved_name: null,
        latitude: null,
        longitude: null,
        trajectory: null,
        ensemble_revision: null,
        trajectory_points: [],
        current_value: null,
        previous_value: null,
        revision_delta: null,
        units: null,
        bust_probability: null,
        previous_bust_probability: null,
        bust_probability_delta: null,
        risk_level: null,
        history_is_durable: false,
        history_source: null,
        abstain: true,
        reason_codes: ['INVALID_LOCATION'],
      }),
    });

    render(<ForecastRevisionPanel initialLocation="Atlantis" />);

    await waitFor(() => {
      expect(screen.getByText(/SAFETY ABSTENTION ACTIVE — NO FORECAST REVISION COMPUTED/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/INVALID_LOCATION/i)).toBeInTheDocument();
    expect(screen.queryByText(/RUN-TO-RUN REVISION/i)).not.toBeInTheDocument();
  });

  it('updates scope indicators when horizon changes from 24h to 264h', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse({
        lead_hours: 264,
        is_certified_horizon: false,
        scientific_scope: 'EXTENDED_OPERATIONAL_HORIZON',
      }),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" initialLeadHours={264} />);

    await waitFor(() => {
      expect(screen.getByText(/Extended Operational Horizon \(264h–384h\)/i)).toBeInTheDocument();
    });
  });

  it('uses frozen benchmark scope wording without claiming live certification', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse(),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" initialLeadHours={24} />);

    await waitFor(() => {
      expect(screen.getByText(/Within Frozen Benchmark Lead Scope \(<= 240h\)/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Certified Benchmark Horizon/i)).not.toBeInTheDocument();
  });

  it('does not claim that issue-cycle history is genuine without provenance', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse({
        status: 'INSUFFICIENT_HISTORY',
        trajectory: null,
        ensemble_revision: null,
        trajectory_points: [],
        history_is_durable: false,
        history_source: null,
      }),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/durable, provider-verified forecast runs/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/genuine issue cycles/i)).not.toBeInTheDocument();
  });

  it('handles variable changes and displays updated units', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse({
        variable: 'wind_speed_10m',
        trajectory: {
          current_value: 6.8,
          previous_value: 5.2,
          revision_delta: 1.6,
          absolute_revision: 1.6,
          direction: 'INCREASED',
        },
        units: {
          value: 'm/s',
          revision_delta: 'm/s',
          absolute_revision: 'm/s',
          ensemble_mean: 'm/s',
          ensemble_spread: 'm/s',
        },
      }),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" initialVariable="wind_speed_10m" />);

    await waitFor(() => {
      expect(screen.getByText('5.2 m/s')).toBeInTheDocument();
    });

    expect(screen.getByText('6.8 m/s')).toBeInTheDocument();
    expect(screen.getByText('+1.6 m/s')).toBeInTheDocument();
  });

  it('displays discrete trajectory points when >= 2 points exist without fake curves', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse(),
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/REAL ISSUE-CYCLE TRAJECTORY EVOLUTION/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/CYCLE 1 \(PRIOR RUN\)/i)).toBeInTheDocument();
    expect(screen.getByText(/CYCLE 2 \(CURRENT RUN\)/i)).toBeInTheDocument();
    expect(screen.getByText(/No synthetic intermediate points or smoothed fake curves are generated/i)).toBeInTheDocument();
  });

  it('handles error state properly and displays error message', async () => {
    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      error: {
        error: 'REVISION_FETCH_FAILED',
        message: 'Internal processing error in revision service',
        status_code: 500,
      },
    });

    render(<ForecastRevisionPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/Internal processing error in revision service/i)).toBeInTheDocument();
    });
  });

  it('triggers cross-navigation callbacks when navigation buttons are clicked', async () => {
    const onNavDisagreement = vi.fn();
    const onNavMulti = vi.fn();

    vi.spyOn(apiClient, 'getForecastRevision').mockResolvedValue({
      data: createMockRevisionResponse(),
    });

    render(
      <ForecastRevisionPanel
        initialLocation="Kolkata"
        onNavigateToDisagreement={onNavDisagreement}
        onNavigateToMultiLocation={onNavMulti}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/View Day 29 Forecast Disagreement/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/View Day 29 Forecast Disagreement/i));
    expect(onNavDisagreement).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText(/View Day 28 Multi-Location Matrix/i));
    expect(onNavMulti).toHaveBeenCalledTimes(1);
  });
});
