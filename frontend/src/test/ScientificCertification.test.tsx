import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VeyraApiClient } from '../api/client';
import { PredictionResult } from '../components/PredictionResult';
import { PredictionResponse } from '../api/types';

describe('Scientific Certification Frontend Integration Tests', () => {
  let client: VeyraApiClient;

  beforeEach(() => {
    client = new VeyraApiClient('http://127.0.0.1:8000');
    vi.restoreAllMocks();
  });

  it('fetches certification policy metadata from backend', async () => {
    const mockPolicy = {
      certification_policy_version: '1.0.0',
      evidence_source: 'DAY22_DAY23_BENCHMARK_EVIDENCE',
      certified_scope: {
        synoptic_stations: ['Mumbai', 'Delhi', 'Kolkata'],
        surface_variables: ['temperature_2m', 'wind_speed_10m', 'surface_pressure'],
        max_lead_hours: 240,
        evaluation_years: [2017, 2019],
        station_count: 25,
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockPolicy,
    } as Response);

    const res = await client.getCertificationPolicy();
    expect(res.data).toEqual(mockPolicy);
    expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8000/v1/certification/policy', expect.anything());
  });

  it('evaluates certification request via API client', async () => {
    const mockCertResult = {
      certification_status: 'CERTIFIED',
      certification_reason: 'Request lies within frozen benchmark evidence boundary.',
      certification_policy_version: '1.0.0',
      is_certified: true,
      model_sha256_verified: true,
      calibrator_sha256_verified: true,
      certified_scope: {
        synoptic_stations: ['Mumbai'],
        surface_variables: ['temperature_2m'],
        max_lead_hours: 240,
        evaluation_years: [2017, 2019],
        station_count: 25,
      },
      observed_scope: {
        location: 'Mumbai',
        resolved_station: 'Mumbai',
        is_synoptic_station: true,
        variable: 'temperature_2m',
        lead_hours: 24,
        model_version: 'v3_lightgbm_isotonic',
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockCertResult,
    } as Response);

    const res = await client.evaluateCertification({
      location: 'Mumbai',
      variable: 'temperature_2m',
      lead_hours: 24,
    });
    expect(res.data?.certification_status).toBe('CERTIFIED');
    expect(res.data?.is_certified).toBe(true);
  });

  it('renders CERTIFIED EVIDENCE SCOPE badge when prediction is certified', () => {
    const mockPrediction: PredictionResponse = {
      location: 'Mumbai',
      bust_probability: 0.12,
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['NOMINAL_PIPELINE'],
      model_version: 'v3_lightgbm_isotonic',
      data_version: 'v3',
      explanation: null,
      certification: {
        certification_status: 'CERTIFIED',
        certification_reason: 'Request lies within frozen benchmark evidence boundary.',
        certification_policy_version: '1.0.0',
        is_certified: true,
        model_sha256_verified: true,
        calibrator_sha256_verified: true,
        certified_scope: {
          synoptic_stations: ['Mumbai'],
          surface_variables: ['temperature_2m'],
          max_lead_hours: 240,
          evaluation_years: [2017, 2019],
          station_count: 25,
        },
        observed_scope: {
          location: 'Mumbai',
          resolved_station: 'Mumbai',
          is_synoptic_station: true,
          variable: 'temperature_2m',
          lead_hours: 24,
          model_version: 'v3_lightgbm_isotonic',
        },
      },
    };

    render(<PredictionResult prediction={mockPrediction} />);
    expect(screen.getByText('CERTIFIED EVIDENCE SCOPE')).toBeInTheDocument();
  });

  it('renders OUTSIDE CERTIFIED EVIDENCE SCOPE badge when prediction is outside certified scope', () => {
    const mockPrediction: PredictionResponse = {
      location: 'Tokyo',
      bust_probability: 0.45,
      risk_level: 'MEDIUM',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['NOMINAL_PIPELINE'],
      model_version: 'v3_lightgbm_isotonic',
      data_version: 'v3',
      explanation: null,
      certification: {
        certification_status: 'OUTSIDE_CERTIFIED_SCOPE',
        certification_reason: 'Location Tokyo is not among the 25 benchmark synoptic stations.',
        certification_policy_version: '1.0.0',
        is_certified: false,
        model_sha256_verified: true,
        calibrator_sha256_verified: true,
        certified_scope: {
          synoptic_stations: ['Mumbai'],
          surface_variables: ['temperature_2m'],
          max_lead_hours: 240,
          evaluation_years: [2017, 2019],
          station_count: 25,
        },
        observed_scope: {
          location: 'Tokyo',
          resolved_station: null,
          is_synoptic_station: false,
          variable: 'temperature_2m',
          lead_hours: 24,
          model_version: 'v3_lightgbm_isotonic',
        },
      },
    };

    render(<PredictionResult prediction={mockPrediction} />);
    expect(screen.getByText('OUTSIDE CERTIFIED EVIDENCE SCOPE')).toBeInTheDocument();
  });
});
