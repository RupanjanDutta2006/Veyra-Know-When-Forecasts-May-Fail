import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SpatialReliabilityPanel } from '../components/SpatialReliabilityPanel';
import { apiClient } from '../api/client';
import { SpatialReliabilityResponse } from '../api/types';


// Mock react-leaflet components for jsdom testing
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: any) => <div data-testid="mock-map-container">{children}</div>,
  TileLayer: () => <div data-testid="mock-tile-layer" />,
  CircleMarker: ({ children, eventHandlers, center, pathOptions }: any) => (
    <div
      data-testid="mock-circle-marker"
      data-lat={center[0]}
      data-lon={center[1]}
      data-color={pathOptions?.fillColor}
      onClick={eventHandlers?.click}
      role="button"
      tabIndex={0}
    >
      {children}
    </div>
  ),
  Popup: ({ children }: any) => <div data-testid="mock-popup">{children}</div>,
  useMap: () => ({
    setView: vi.fn(),
    fitBounds: vi.fn(),
  }),
}));

const createMockSpatialResponse = (
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
      dominant_risk_drivers: ['HIGH_ENSEMBLE_AGREEMENT'],
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
      dominant_risk_drivers: ['MILD_ENSEMBLE_SPREAD'],
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
      trust_state: 'MODERATE_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      calibration_status: 'CALIBRATED',
      model_version: 'v3_lightgbm_challenger',
      data_version: 'v1.0',
      is_certified_horizon: true,
      scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
      dominant_risk_drivers: ['COASTAL_GRADIENT'],
    },
    {
      location: 'Chennai',
      resolved_name: 'Chennai',
      latitude: 13.0827,
      longitude: 80.2707,
      region_id: 'IN_CHENNAI',
      variable: 'temperature_2m',
      lead_hours: 24,
      lead_days: 1.0,
      issue_time: '2026-09-19T06:00:00Z',
      valid_time: '2026-09-20T06:00:00Z',
      bust_probability: 0.88,
      risk_level: 'CRITICAL',
      trust_state: 'LOW_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      calibration_status: 'CALIBRATED',
      model_version: 'v3_lightgbm_challenger',
      data_version: 'v1.0',
      is_certified_horizon: true,
      scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
      dominant_risk_drivers: ['STRONG_DIVERGENCE'],
    },
  ],
  summary: {
    total_locations: 4,
    available_locations: 4,
    abstained_locations: 0,
    max_bust_probability: 0.88,
    max_risk_level: 'CRITICAL',
    max_risk_location: 'Chennai',
    mean_bust_probability: 0.4925,
    elevated_risk_locations: 3,
  },
  ...overrides,
});

describe('SpatialReliabilityPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the spatial reliability header and scientific principles notice', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockSpatialResponse(),
    });

    render(<SpatialReliabilityPanel />);

    expect(screen.getByText('Spatial Forecast Reliability Intelligence')).toBeInTheDocument();
    expect(
      screen.getByText(/No continuous surfaces or geographic interpolation/i)
    ).toBeInTheDocument();
  });

  it('renders discrete markers corresponding to evaluated valid points', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockSpatialResponse(),
    });

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      const markers = screen.getAllByTestId('mock-circle-marker');
      expect(markers).toHaveLength(4);
    });

    // Verify coordinates on markers
    const markers = screen.getAllByTestId('mock-circle-marker');
    expect(markers[0]).toHaveAttribute('data-lat', '22.5726');
    expect(markers[0]).toHaveAttribute('data-lon', '88.3639');
    expect(markers[0]).toHaveAttribute('data-color', '#10b981'); // LOW = green
    expect(markers[3]).toHaveAttribute('data-color', '#8b5cf6'); // CRITICAL = purple
  });

  it('displays summary metrics matching backend summary', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockSpatialResponse(),
    });

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      expect(screen.getByText('PEAK P(BUST)')).toBeInTheDocument();
    });

    expect(screen.getAllByText('88.0%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Chennai').length).toBeGreaterThan(0);
    expect(screen.getByText('49.3%')).toBeInTheDocument(); // Mean prob (49.25% rounded)
    expect(screen.getByText('3')).toBeInTheDocument(); // Elevated risk locations


  });

  it('updates selected station card when clicking a marker', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockSpatialResponse(),
    });

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      expect(screen.getAllByTestId('mock-circle-marker')).toHaveLength(4);
    });

    // Click Delhi marker (index 1)
    const markers = screen.getAllByTestId('mock-circle-marker');
    fireEvent.click(markers[1]);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Delhi' })).toBeInTheDocument();
      expect(screen.getByText('MEDIUM RISK')).toBeInTheDocument();
    });
    expect(screen.getAllByText('35.0%').length).toBeGreaterThan(0);
  });

  it('safely handles mixed valid and unresolvable/abstained locations without plotting at (0,0)', async () => {
    const mixedResponse = createMockSpatialResponse({
      points: [
        {
          location: 'Kolkata',
          resolved_name: 'Kolkata',
          latitude: 22.5726,
          longitude: 88.3639,
          variable: 'temperature_2m',
          lead_hours: 24,
          lead_days: 1.0,
          bust_probability: 0.12,
          risk_level: 'LOW',
          trust_state: 'HIGH_CONFIDENCE',
          abstain: false,
          reason_codes: ['SUCCESS'],
          is_certified_horizon: true,
          scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
        },
        {
          location: 'Atlantis',
          resolved_name: null,
          latitude: null,
          longitude: null,
          variable: 'temperature_2m',
          lead_hours: 24,
          lead_days: 1.0,
          bust_probability: null,
          risk_level: null,
          trust_state: 'UNAVAILABLE',
          abstain: true,
          reason_codes: ['INVALID_LOCATION'],
          is_certified_horizon: true,
          scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
        },
      ],
      summary: {
        total_locations: 2,
        available_locations: 1,
        abstained_locations: 1,
        max_bust_probability: 0.12,
        max_risk_level: 'LOW',
        max_risk_location: 'Kolkata',
        mean_bust_probability: 0.12,
        elevated_risk_locations: 0,
      },
    });

    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: mixedResponse,
    });

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      // Only 1 marker plotted on map (Kolkata), Atlantis must NOT be plotted
      const markers = screen.getAllByTestId('mock-circle-marker');
      expect(markers).toHaveLength(1);
    });

    // Atlantis should be listed in the unresolvable drawer
    expect(screen.getByText(/Unresolvable \/ Abstained Locations/i)).toBeInTheDocument();
    expect(screen.getByText('Atlantis')).toBeInTheDocument();
    expect(screen.getByText('INVALID_LOCATION')).toBeInTheDocument();
  });

  it('handles null probability safety without coercion to 0% or LOW', async () => {
    const allAbstainedResponse = createMockSpatialResponse({
      status: 'ABSTAINED',
      points: [
        {
          location: 'Atlantis',
          latitude: null,
          longitude: null,
          variable: 'temperature_2m',
          lead_hours: 24,
          lead_days: 1.0,
          bust_probability: null,
          risk_level: null,
          trust_state: 'UNAVAILABLE',
          abstain: true,
          reason_codes: ['INVALID_LOCATION'],
          is_certified_horizon: true,
          scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
        },
      ],
      summary: {
        total_locations: 1,
        available_locations: 0,
        abstained_locations: 1,
        max_bust_probability: null,
        max_risk_level: null,
        max_risk_location: null,
        mean_bust_probability: null,
        elevated_risk_locations: 0,
      },
    });

    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: allAbstainedResponse,
    });

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      // Must render 'N/A', NOT '0.0%' or 'LOW'
      const peakMetrics = screen.getAllByText('N/A');
      expect(peakMetrics.length).toBeGreaterThan(0);
    });
  });

  it('triggers a new backend evaluation when changing variable', async () => {
    const spy = vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockSpatialResponse(),
    });

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Refresh Spatial Intelligence/i })).toBeInTheDocument();
    });

    // Change variable to wind_speed_10m
    const varSelect = screen.getByLabelText('Meteorological Variable');
    fireEvent.change(varSelect, { target: { value: 'wind_speed_10m' } });

    // Click refresh
    const refreshBtn = screen.getByRole('button', { name: /Refresh Spatial Intelligence/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(2);
      expect(spy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          variable: 'wind_speed_10m',
        })
      );
    });
  });

  it('distinguishes benchmark scope (<=240h) from extended operational horizon (>240h)', async () => {
    vi.spyOn(apiClient, 'getSpatialReliability').mockResolvedValue({
      data: createMockSpatialResponse({
        lead_hours: 384,
        is_certified_horizon: false,
        scientific_scope: 'EXTENDED_OPERATIONAL_HORIZON',
      }),
    });

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Refresh Spatial Intelligence/i })).toBeInTheDocument();
    });

    // Switch horizon to 384h
    const horizonSelect = screen.getByLabelText(/Forecast Lead Horizon/i);
    fireEvent.change(horizonSelect, { target: { value: '384' } });

    // Refresh
    const refreshBtn = screen.getByRole('button', { name: /Refresh Spatial Intelligence/i });
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

    render(<SpatialReliabilityPanel />);

    await waitFor(() => {
      expect(screen.getByText('Spatial Query Alert')).toBeInTheDocument();
      expect(screen.getByText(/Backend server timeout/i)).toBeInTheDocument();
    });
  });


});
