import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ForecastDisagreementPanel } from '../components/ForecastDisagreementPanel';
import { apiClient } from '../api/client';
import { ForecastDisagreementResponse } from '../api/types';

const createMockDisagreementResponse = (
  overrides?: Partial<ForecastDisagreementResponse>
): ForecastDisagreementResponse => ({
  status: 'AVAILABLE',
  variable: 'temperature_2m',
  lead_hours: 24,
  lead_days: 1.0,
  location: 'Kolkata',
  latitude: 22.57,
  longitude: 88.36,
  issue_time: '2026-09-19T06:00:00Z',
  valid_time: '2026-09-20T06:00:00Z',
  member_count: 31,
  has_full_ensemble: true,
  bust_probability: 0.142,
  risk_level: 'LOW',
  trust_state: 'HIGH_CONFIDENCE',
  calibration_status: 'CALIBRATED_ISOTONIC',
  scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
  is_certified_horizon: true,
  abstain: false,
  reason_codes: [],
  request_id: 'disagree-test-req-001',
  diagnostics: {
    ensemble_spread: 2.41,
    ensemble_std: 2.41,
    ensemble_range: 7.80,
    ensemble_iqr: 3.10,
    ensemble_cv: 0.0825,
    spread_to_iqr_ratio: 0.777,
    ensemble_mean: 28.5,
    ensemble_min: 24.1,
    ensemble_max: 31.9,
  },
  units: {
    spread: '°C',
    range: '°C',
    iqr: '°C',
    cv: 'dimensionless',
    spread_to_iqr_ratio: 'dimensionless',
    mean: '°C',
  },
  ...overrides,
});

describe('ForecastDisagreementPanel Component (Day 29)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the header with Day 29 badge and NOAA GEFS member count', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement').mockResolvedValue({
      data: createMockDisagreementResponse(),
    });

    render(<ForecastDisagreementPanel initialLocation="Kolkata" />);

    expect(screen.getByText(/FORECAST DISAGREEMENT INTELLIGENCE/i)).toBeInTheDocument();
    expect(screen.getByText(/DAY 29/i)).toBeInTheDocument();
    expect(screen.getByText(/NOAA GEFS • 31 Members/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/CALIBRATED FAILURE RISK/i)).toBeInTheDocument();
    });
  });

  it('strictly separates calibrated P(BUST) from ensemble spread diagnostics', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement').mockResolvedValue({
      data: createMockDisagreementResponse({
        bust_probability: 0.142,
        risk_level: 'LOW',
        diagnostics: {
          ensemble_spread: 2.41,
          ensemble_std: 2.41,
          ensemble_range: 7.80,
          ensemble_iqr: 3.10,
          ensemble_cv: 0.0825,
          spread_to_iqr_ratio: 0.78,
          ensemble_mean: 28.5,
          ensemble_min: 24.1,
          ensemble_max: 31.9,
        },
      }),
    });

    render(<ForecastDisagreementPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(apiClient.getForecastDisagreement).toHaveBeenCalled();
      expect(screen.getByText(/CALIBRATED FAILURE RISK/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/14\.2%/)).toBeInTheDocument();
    expect(screen.getByText('P(BUST)')).toBeInTheDocument();
    expect(screen.getByText('LOW RISK')).toBeInTheDocument();
    expect(screen.getAllByText(/OBSERVED ENSEMBLE SPREAD/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders all real dispersion metrics with physical units and no synthetic tiers', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement').mockResolvedValue({
      data: createMockDisagreementResponse({
        variable: 'temperature_2m',
        diagnostics: {
          ensemble_spread: 2.41,
          ensemble_std: 2.41,
          ensemble_range: 7.80,
          ensemble_iqr: 3.10,
          ensemble_cv: 0.0825,
          spread_to_iqr_ratio: 0.78,
          ensemble_mean: 28.5,
          ensemble_min: 24.1,
          ensemble_max: 31.9,
        },
      }),
    });

    render(<ForecastDisagreementPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/ENSEMBLE DISPERSION METRICS DETAIL/i)).toBeInTheDocument();
      expect(screen.getByText('2.41 °C')).toBeInTheDocument();
      expect(screen.getByText('7.80 °C')).toBeInTheDocument();
      expect(screen.getByText('3.10 °C')).toBeInTheDocument();
      expect(screen.getByText('0.0825')).toBeInTheDocument();
      expect(screen.getByText('0.78')).toBeInTheDocument();
      expect(screen.getByText('28.5 °C')).toBeInTheDocument();
      expect(screen.getByText(/Min: 24.1 \| Max: 31.9/i)).toBeInTheDocument();
    });
  });

  it('adapts physical units when switching atmospheric variables', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement')
      .mockResolvedValueOnce({
        data: createMockDisagreementResponse({
          variable: 'temperature_2m',
          units: {
            spread: '°C',
            range: '°C',
            iqr: '°C',
            cv: 'dimensionless',
            spread_to_iqr_ratio: 'dimensionless',
            mean: '°C',
          },
        }),
      })
      .mockResolvedValueOnce({
        data: createMockDisagreementResponse({
          variable: 'wind_speed_10m',
          diagnostics: {
            ensemble_spread: 1.85,
            ensemble_std: 1.85,
            ensemble_range: 6.20,
            ensemble_iqr: 2.10,
            ensemble_cv: 0.28,
            spread_to_iqr_ratio: 0.88,
            ensemble_mean: 6.5,
            ensemble_min: 3.2,
            ensemble_max: 9.4,
          },
          units: {
            spread: 'm/s',
            range: 'm/s',
            iqr: 'm/s',
            cv: 'dimensionless',
            spread_to_iqr_ratio: 'dimensionless',
            mean: 'm/s',
          },
        }),
      });

    render(<ForecastDisagreementPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText('2.41 °C')).toBeInTheDocument();
    });

    const varSelect = screen.getByLabelText(/ATMOSPHERIC VARIABLE/i);
    fireEvent.change(varSelect, { target: { value: 'wind_speed_10m' } });

    await waitFor(() => {
      expect(screen.getByText('1.85 m/s')).toBeInTheDocument();
    });
  });

  it('preserves scientific scope semantics for <=240h vs 264h-384h', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement')
      .mockResolvedValueOnce({
        data: createMockDisagreementResponse({
          lead_hours: 240,
          scientific_scope: 'FROZEN_BENCHMARK_LEAD_SCOPE',
        }),
      })
      .mockResolvedValueOnce({
        data: createMockDisagreementResponse({
          lead_hours: 264,
          scientific_scope: 'EXTENDED_OPERATIONAL_HORIZON',
        }),
      });

    render(<ForecastDisagreementPanel initialLocation="Kolkata" initialLeadHours={240} />);

    await waitFor(() => {
      expect(screen.getByText(/WITHIN FROZEN BENCHMARK LEAD SCOPE/i)).toBeInTheDocument();
    });

    const horizonSelect = screen.getByLabelText(/LEAD HORIZON/i);
    fireEvent.change(horizonSelect, { target: { value: '264' } });

    await waitFor(() => {
      expect(screen.getByText(/EXTENDED OPERATIONAL HORIZON/i)).toBeInTheDocument();
    });
  });

  it('safely handles operational abstention without fabricating default zeroes', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement').mockResolvedValue({
      data: createMockDisagreementResponse({
        status: 'UNAVAILABLE',
        location: 'Atlantis',
        latitude: null,
        longitude: null,
        member_count: null,
        bust_probability: null,
        risk_level: null,
        trust_state: 'ABSTAINED',
        abstain: true,
        reason_codes: ['LOCATION_NOT_RESOLVED: Atlantis'],
        diagnostics: null,
      }),
    });

    render(<ForecastDisagreementPanel initialLocation="Atlantis" />);

    await waitFor(() => {
      expect(screen.getByText(/OPERATIONAL ABSTENTION ENFORCED/i)).toBeInTheDocument();
      expect(screen.getByText(/LOCATION_NOT_RESOLVED: Atlantis/i)).toBeInTheDocument();
      // Ensure missing values render as N/A, never 0 or 0%
      expect(screen.getByText('ABSTAINED RISK')).toBeInTheDocument();
      expect(screen.getAllByText('N/A').length).toBeGreaterThanOrEqual(1);
      expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
    });
  });

  it('triggers navigation callbacks for cross-view integration with Day 27 & Day 28', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement').mockResolvedValue({
      data: createMockDisagreementResponse(),
    });

    const mockSpatialNav = vi.fn();
    const mockMultiLocNav = vi.fn();

    render(
      <ForecastDisagreementPanel
        initialLocation="Kolkata"
        onNavigateToSpatial={mockSpatialNav}
        onNavigateToMultiLocation={mockMultiLocNav}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Multi-Location View \(Day 28\)/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Multi-Location View \(Day 28\)/i));
    expect(mockMultiLocNav).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText(/Spatial Map \(Day 27\)/i));
    expect(mockSpatialNav).toHaveBeenCalledTimes(1);
  });
});

describe('Day 38 Cross-Provider Disagreement Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. API client has getCrossProviderDisagreement method', () => {
    expect(typeof apiClient.getCrossProviderDisagreement).toBe('function');
  });

  it('2-3. API client posts to /v1/provider-disagreement/diagnostics with typed request', async () => {
    const mockFetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: 'AVAILABLE',
        reason_code: 'OK',
        canonical_location: 'Kolkata',
        variable: 'temperature_2m',
        valid_time: '2026-09-21T06:00:00Z',
        unit: '°C',
        primary_provider: {
          provider_id: 'openmeteo_gefs',
          provider_name: 'Open-Meteo GEFS',
          provider_source_mode: 'LIVE',
          canonical_location: 'Kolkata',
          issue_time: '2026-09-20T06:00:00Z',
          valid_time: '2026-09-21T06:00:00Z',
          lead_hours: 24,
          variable: 'temperature_2m',
          forecast_value: 32.5,
          unit: '°C',
          is_available: true,
        },
        secondary_provider: {
          provider_id: 'fixture_second_provider',
          provider_name: 'Fixture Second Provider',
          provider_source_mode: 'FIXTURE',
          canonical_location: 'Kolkata',
          issue_time: '2026-09-20T06:00:00Z',
          valid_time: '2026-09-21T06:00:00Z',
          lead_hours: 24,
          variable: 'temperature_2m',
          forecast_value: 30.0,
          unit: '°C',
          is_available: true,
        },
        signed_difference: 2.5,
        absolute_difference: 2.5,
        provider_min: 30.0,
        provider_max: 32.5,
        provider_mean: 31.25,
        relative_difference_pct: 8.33,
        is_comparable: true,
        has_fixture_provider: true,
        provenance_notice: 'Secondary provider uses deterministic fixture data for validation.',
        scope_note: 'Diagnostic comparison between normalized provider values.',
      }),
    } as Response);

    const res = await apiClient.getCrossProviderDisagreement({
      location: 'Kolkata',
      variable: 'temperature_2m',
      lead_hours: 24,
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/v1/provider-disagreement/diagnostics'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          location: 'Kolkata',
          variable: 'temperature_2m',
          lead_hours: 24,
        }),
      })
    );
    expect(res.data?.status).toBe('AVAILABLE');
    expect(res.data?.absolute_difference).toBe(2.5);
  });

  it('4-12. CrossProviderDisagreementPanel renders values, differences, units, and fixture provenance disclosure', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement').mockResolvedValue({
      data: createMockDisagreementResponse(),
    });

    vi.spyOn(apiClient, 'getCrossProviderDisagreement').mockResolvedValue({
      data: {
        status: 'AVAILABLE',
        reason_code: 'OK',
        canonical_location: 'Kolkata',
        variable: 'temperature_2m',
        valid_time: '2026-09-21T06:00:00Z',
        unit: '°C',
        primary_provider: {
          provider_id: 'openmeteo_gefs',
          provider_name: 'Open-Meteo GEFS',
          provider_source_mode: 'LIVE',
          canonical_location: 'Kolkata',
          issue_time: '2026-09-20T06:00:00Z',
          valid_time: '2026-09-21T06:00:00Z',
          lead_hours: 24,
          variable: 'temperature_2m',
          forecast_value: 32.5,
          unit: '°C',
          is_available: true,
        },
        secondary_provider: {
          provider_id: 'fixture_second_provider',
          provider_name: 'Fixture Second Provider',
          provider_source_mode: 'FIXTURE',
          canonical_location: 'Kolkata',
          issue_time: '2026-09-20T06:00:00Z',
          valid_time: '2026-09-21T06:00:00Z',
          lead_hours: 24,
          variable: 'temperature_2m',
          forecast_value: 30.0,
          unit: '°C',
          is_available: true,
        },
        signed_difference: 2.5,
        absolute_difference: 2.5,
        provider_min: 30.0,
        provider_max: 32.5,
        provider_mean: 31.25,
        relative_difference_pct: 8.33,
        is_comparable: true,
        has_fixture_provider: true,
        provenance_notice: 'Secondary provider uses deterministic fixture data for validation.',
        scope_note: 'Diagnostic comparison between normalized provider values.',
      },
    });

    render(<ForecastDisagreementPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/Cross-Provider Forecast Difference/i)).toBeInTheDocument();
      expect(screen.getByText(/Secondary Provider: Deterministic Fixture Data/i)).toBeInTheDocument();
      expect(screen.getByText('32.5 °C')).toBeInTheDocument();
      expect(screen.getByText('30 °C')).toBeInTheDocument();
      expect(screen.getByText('2.5 °C')).toBeInTheDocument();
      expect(screen.getByText('+2.5 °C')).toBeInTheDocument();
      expect(screen.getByText('8.33%')).toBeInTheDocument();
    });
  });

  it('13-16. Handles PROVIDER_UNAVAILABLE safely without fake zeroes or raw tracebacks', async () => {
    vi.spyOn(apiClient, 'getForecastDisagreement').mockResolvedValue({
      data: createMockDisagreementResponse(),
    });

    vi.spyOn(apiClient, 'getCrossProviderDisagreement').mockResolvedValue({
      data: {
        status: 'PROVIDER_UNAVAILABLE',
        reason_code: 'PRIMARY_UNAVAILABLE',
        canonical_location: 'Kolkata',
        variable: 'temperature_2m',
        valid_time: '2026-09-21T06:00:00Z',
        unit: '°C',
        primary_provider: null,
        secondary_provider: null,
        signed_difference: null,
        absolute_difference: null,
        provider_min: null,
        provider_max: null,
        provider_mean: null,
        relative_difference_pct: null,
        is_comparable: false,
        has_fixture_provider: true,
        provenance_notice: 'Secondary provider uses deterministic fixture data.',
        scope_note: 'Comparison unavailable due to primary provider timeout.',
      },
    });

    render(<ForecastDisagreementPanel initialLocation="Kolkata" />);

    await waitFor(() => {
      expect(screen.getByText(/PROVIDER_UNAVAILABLE/i)).toBeInTheDocument();
      expect(screen.getAllByText('Unavailable').length).toBeGreaterThanOrEqual(2);
      expect(screen.queryByText('0.0 °C')).not.toBeInTheDocument();
    });
  });
});
