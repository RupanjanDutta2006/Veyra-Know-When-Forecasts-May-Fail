import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MultiLocationPanel } from '../components/MultiLocationPanel';
import { apiClient } from '../api/client';
import { SpatialReliabilityResponse } from '../api/types';

const createMockMultiLocationResponse = (
  overrides?: Partial<SpatialReliabilityResponse>
): SpatialReliabilityResponse => ({
  status: 'SUCCESS',
  variable: 'temperature_2m',
  lead_hours: 24,
  lead_days: 1.0,
  issue_time: '2026-09-19T06:00:00Z',
  is_certified_horizon: true,
  scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
  points: [
    {
      location: 'Kolkata',
      resolved_name: 'Kolkata',
      latitude: 22.5726,
      longitude: 88.3639,
      region_id: 'IN_KOLKATA',
      variable: 'temperature_2m',
      lead_hours: 24,
      lead_days: 1.0,
      issue_time: '2026-09-19T06:00:00Z',
      valid_time: '2026-09-20T06:00:00Z',
      bust_probability: 0.12,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      calibration_status: 'CALIBRATED',
      model_version: 'v3_lightgbm_challenger',
      data_version: 'v1.0',
      is_certified_horizon: true,
      scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
      confidence_index: 0.94,
      uncertainty_pct: 4.2,
      dominant_risk_drivers: ['HIGH_ENSEMBLE_AGREEMENT'],
      decision_mode: 'ROUTINE',
      decision_guidance: 'Forecast reliable for standard operations.',
    },
    {
      location: 'Delhi',
      resolved_name: 'Delhi',
      latitude: 28.6139,
      longitude: 77.2090,
      region_id: 'IN_DELHI',
      variable: 'temperature_2m',
      lead_hours: 24,
      lead_days: 1.0,
      issue_time: '2026-09-19T06:00:00Z',
      valid_time: '2026-09-20T06:00:00Z',
      bust_probability: 0.35,
      risk_level: 'MEDIUM',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      calibration_status: 'CALIBRATED',
      model_version: 'v3_lightgbm_challenger',
      data_version: 'v1.0',
      is_certified_horizon: true,
      scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
      confidence_index: 0.82,
      uncertainty_pct: 12.8,
      dominant_risk_drivers: ['MILD_ENSEMBLE_SPREAD'],
      decision_mode: 'MONITORING',
      decision_guidance: 'Elevated bust risk; monitor subsequent synoptic cycles.',
    },
    {
      location: 'Mumbai',
      resolved_name: 'Mumbai',
      latitude: 19.0760,
      longitude: 72.8777,
      region_id: 'IN_MUMBAI',
      variable: 'temperature_2m',
      lead_hours: 24,
      lead_days: 1.0,
      issue_time: '2026-09-19T06:00:00Z',
      valid_time: '2026-09-20T06:00:00Z',
      bust_probability: 0.62,
      risk_level: 'HIGH',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      calibration_status: 'CALIBRATED',
      model_version: 'v3_lightgbm_challenger',
      data_version: 'v1.0',
      is_certified_horizon: true,
      scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
      confidence_index: 0.65,
      uncertainty_pct: 22.4,
      dominant_risk_drivers: ['HIGH_ENSEMBLE_SPREAD'],
      decision_mode: 'ACTIVE_WARNING',
      decision_guidance: 'Significant likelihood of numerical forecast failure.',
    },
    {
      location: 'Atlantis',
      resolved_name: null,
      latitude: null,
      longitude: null,
      region_id: null,
      variable: 'temperature_2m',
      lead_hours: 24,
      lead_days: 1.0,
      issue_time: '2026-09-19T06:00:00Z',
      valid_time: '2026-09-20T06:00:00Z',
      bust_probability: null,
      risk_level: null,
      trust_state: 'UNAVAILABLE',
      abstain: true,
      reason_codes: ['INVALID_LOCATION'],
      calibration_status: 'UNAVAILABLE',
      model_version: 'v3_lightgbm_challenger',
      data_version: 'v1.0',
      is_certified_horizon: true,
      scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
    },
  ],
  summary: {
    total_locations: 4,
    available_locations: 3,
    abstained_locations: 1,
    max_bust_probability: 0.62,
    max_risk_level: 'HIGH',
    max_risk_location: 'Mumbai',
    mean_bust_probability: 0.3633,
    elevated_risk_locations: 2,
    low_risk_locations: 1,
    medium_risk_locations: 1,
    high_risk_locations: 1,
    critical_risk_locations: 0,
  },
  request_id: 'req_test_multi_123',
  ...overrides,
});

describe('MultiLocationPanel Component (Day 28)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the multi-location header and scientific principles disclaimer', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel />);

    expect(screen.getByText('Multi-Location Reliability Intelligence')).toBeInTheDocument();
    expect(screen.getByText(/Objective reliability comparison/i)).toBeInTheDocument();
    expect(screen.getAllByText(/WITHIN FROZEN BENCHMARK LEAD SCOPE/i).length).toBeGreaterThan(0);
  });

  it('renders multiple location cards with calibrated P(BUST) and risk badges', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getAllByText('Kolkata').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Delhi').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Mumbai').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Atlantis').length).toBeGreaterThan(0);
      expect(screen.getAllByText('12.0%').length).toBeGreaterThan(0);
      expect(screen.getAllByText('35.0%').length).toBeGreaterThan(0);
      expect(screen.getAllByText('62.0%').length).toBeGreaterThan(0);
      expect(screen.getAllByText('LOW RISK').length).toBeGreaterThan(0);
      expect(screen.getAllByText('MEDIUM RISK').length).toBeGreaterThan(0);
      expect(screen.getAllByText('HIGH RISK').length).toBeGreaterThan(0);
    });
  });

  it('displays summary metrics matching backend summary accurately', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getByText('TOTAL EVALUATED')).toBeInTheDocument();
      expect(screen.getByText('HIGHEST EVALUATED P(BUST)')).toBeInTheDocument();
      expect(screen.getByText('MEAN BUST PROBABILITY')).toBeInTheDocument();
      expect(screen.getByText('ELEVATED RISK LOCATIONS')).toBeInTheDocument();
      expect(screen.getByText('36.3%')).toBeInTheDocument();
      expect(screen.getByText('3 Available | 1 Abstained')).toBeInTheDocument();
    });
  });

  it('toggles between cards view and dense table view', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getAllByText('Kolkata').length).toBeGreaterThan(0);
    });

    // Toggle to Table view
    const tableBtn = screen.getByTitle('Dense Table View');
    fireEvent.click(tableBtn);

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Coordinates')).toBeInTheDocument();
    expect(screen.getByText('Dominant Driver')).toBeInTheDocument();

    // Toggle back to Cards view
    const cardsBtn = screen.getByTitle('Grid Cards View');
    fireEvent.click(cardsBtn);

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('filters locations by risk tier', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getAllByText('Kolkata').length).toBeGreaterThan(0);
    });

    // Filter by Elevated Risk (Delhi and Mumbai only)
    const elevatedBtn = screen.getByRole('button', { name: /Elevated Risk \(2\)/i });
    fireEvent.click(elevatedBtn);

    expect(screen.queryByTestId('location-card-Kolkata')).not.toBeInTheDocument();
    expect(screen.getByTestId('location-card-Delhi')).toBeInTheDocument();
    expect(screen.getByTestId('location-card-Mumbai')).toBeInTheDocument();

    // Filter by Low (Kolkata only)
    const lowBtn = screen.getByRole('button', { name: /Low \(1\)/i });
    fireEvent.click(lowBtn);

    expect(screen.getByTestId('location-card-Kolkata')).toBeInTheDocument();
    expect(screen.queryByTestId('location-card-Delhi')).not.toBeInTheDocument();
    expect(screen.queryByTestId('location-card-Mumbai')).not.toBeInTheDocument();
  });

  it('safely handles unresolvable / abstained locations without coercing to 0% or LOW', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('location-card-Atlantis')).toBeInTheDocument();
      // Atlantis should show ABSTAINED or INVALID_LOCATION, never 0.0%
      expect(screen.getAllByText(/ABSTAINED/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/INVALID_LOCATION/i).length).toBeGreaterThan(0);
    });
  });

  it('inspects selected location and displays diagnostics and physical drivers', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('location-card-Delhi')).toBeInTheDocument();
    });

    // Click on Delhi card to select it
    const delhiCard = screen.getByTestId('location-card-Delhi');
    fireEvent.click(delhiCard);

    await waitFor(() => {
      expect(screen.getByText('Location Diagnostic Inspector')).toBeInTheDocument();
      expect(screen.getAllByText('MILD_ENSEMBLE_SPREAD').length).toBeGreaterThan(0);
      expect(screen.getByText(/Elevated bust risk; monitor subsequent synoptic cycles/i)).toBeInTheDocument();
    });
  });

  it('triggers real backend evaluation when switching variable and horizon', async () => {
    const spy = vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse({
        variable: 'wind_speed_10m',
        lead_hours: 240,
      }),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(1);
    });

    // Change variable to wind_speed_10m
    const varSelect = screen.getByLabelText('Meteorological Variable');
    fireEvent.change(varSelect, { target: { value: 'wind_speed_10m' } });

    // Change horizon to 240h
    const horizonSelect = screen.getByLabelText(/Forecast Lead Horizon/i);
    fireEvent.change(horizonSelect, { target: { value: '240' } });

    // Click refresh
    const refreshBtn = screen.getByRole('button', { name: /Refresh Multi-Location Intelligence/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(2);
      expect(spy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          variable: 'wind_speed_10m',
          lead_hours: 240,
        })
      );
    });
  });

  it('distinguishes benchmark lead scope (<=240h) from extended operational horizon (>240h)', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse({
        lead_hours: 384,
        is_certified_horizon: false,
        scientific_scope: 'EXTENDED_OPERATIONAL_HORIZON',
      }),
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Refresh Multi-Location Intelligence/i })).toBeInTheDocument();
    });

    // Switch horizon to 384h
    const horizonSelect = screen.getByLabelText(/Forecast Lead Horizon/i);
    fireEvent.change(horizonSelect, { target: { value: '384' } });

    // Refresh
    const refreshBtn = screen.getByRole('button', { name: /Refresh Multi-Location Intelligence/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(screen.getAllByText(/EXTENDED OPERATIONAL/i).length).toBeGreaterThan(0);
    });
  });

  it('displays error alert when API call fails', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      error: {
        error: 'NETWORK_ERROR',
        message: 'Backend server timeout while fetching ensemble data.',
        status_code: 504,
      },
    });

    render(<MultiLocationPanel />);

    await waitFor(() => {
      expect(screen.getByText('Multi-Location Query Alert')).toBeInTheDocument();
      expect(screen.getByText(/Backend server timeout/i)).toBeInTheDocument();
    });
  });

  it('supports cross-navigation to spatial map view', async () => {
    const navSpy = vi.fn();
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockMultiLocationResponse(),
    });

    render(<MultiLocationPanel onNavigateToSpatial={navSpy} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /View on Spatial Map/i })).toBeInTheDocument();
    });

    const mapBtn = screen.getByRole('button', { name: /View on Spatial Map/i });
    fireEvent.click(mapBtn);

    expect(navSpy).toHaveBeenCalled();
  });
});
