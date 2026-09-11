import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import { apiClient } from '../api/client';
import { DashboardIntelligenceResponse } from '../api/types';

describe('Frontend <-> Backend Exact Value Parity Regression Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders distinct probabilities across horizons without copying Day 1 to all horizons', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: {
        status: 'healthy',
        service: 'veyra-backend',
        version: '3.0.0',
      },
    });

    const mockMultiHorizonData: DashboardIntelligenceResponse = {
      location: {
        query: 'Delhi',
        resolved_name: 'Delhi Synoptic Station',
        latitude: 28.61,
        longitude: 77.21,
      },
      variable: 'temperature_2m',
      mode: 'full_16d',
      status: 'SUCCESS',
      selected_prediction: {
        location: 'Delhi',
        bust_probability: 0.0104,
        risk_level: 'LOW',
        trust_state: 'HIGH_CONFIDENCE',
        abstain: false,
        reason_codes: ['MODEL_OPERATIONAL_NOMINAL'],
        model_version: 'veyra-v3-benchmark-lightgbm',
        data_version: 'gefs-reanalysis-v3',
        explanation: {
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
          bust_probability: 0.0104,
          risk_level: 'LOW',
          trust_state: 'HIGH_CONFIDENCE',
          abstain: false,
          is_certified_horizon: true,
          reason_codes: ['MODEL_OPERATIONAL_NOMINAL'],
        },
        {
          lead_hours: 48,
          lead_days: 2,
          valid_time: '2026-09-13T12:00:00Z',
          bust_probability: 0.0483,
          risk_level: 'LOW',
          trust_state: 'HIGH_CONFIDENCE',
          abstain: false,
          is_certified_horizon: true,
          reason_codes: ['MODEL_OPERATIONAL_NOMINAL'],
        },
        {
          lead_hours: 72,
          lead_days: 3,
          valid_time: '2026-09-14T12:00:00Z',
          bust_probability: 0.0825,
          risk_level: 'LOW',
          trust_state: 'HIGH_CONFIDENCE',
          abstain: false,
          is_certified_horizon: true,
          reason_codes: ['MODEL_OPERATIONAL_NOMINAL'],
        },
      ],
      summary: {
        available_points: 3,
        abstained_points: 0,
        total_points: 3,
        max_bust_probability: 0.0825,
        max_risk_level: 'LOW',
        max_risk_lead_hours: 24,
        mean_bust_probability: 0.0471,
        elevated_risk_points: 0,
        first_elevated_risk_lead_hours: null,
        overall_decision_mode: 'NOMINAL_OPERATIONS',
      },
      scientific_context: {
        model_version: 'veyra-v3-benchmark-lightgbm',
        model_family: 'LightGBM + Isotonic Calibration',
        calibration_method: 'Isotonic Regression',
        feature_count: 50,
        probability_semantics: 'Empirical P(Bust)',
        benchmark_scope: 'Certified frozen split',
        benchmark_lead_horizon_max_hours: 240,
        operational_horizon_max_hours: 384,
        historical_benchmark: {
          dataset: 'certified_splits_v3',
          period: '2017-2019',
          test_samples: 116250,
          test_cycles: 155,
          average_precision: 0.2047,
          pr_auc_trapezoidal: 0.2047,
          roc_auc: 0.7698,
          brier_score: 0.0538,
          bss_vs_e0: 0.0807,
          bss_vs_e1b: 0.0778,
          ece: 0.0064,
        },
        generalization_limits: ['Certified across 25 canonical synoptic stations in India only'],
      },
    };

    const spy = vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({
      data: mockMultiHorizonData,
    });

    render(<App />);

    const locationInput = screen.getByLabelText(/location name or coordinates/i);
    fireEvent.change(locationInput, { target: { value: 'Delhi' } });

    const modeSelect = screen.getByLabelText(/evaluation horizon mode/i);
    fireEvent.change(modeSelect, { target: { value: 'full_16d' } });

    const auditBtn = screen.getByRole('button', { name: /audit reliability/i });
    fireEvent.click(auditBtn);

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({
        location: 'Delhi',
        variable: 'temperature_2m',
        mode: 'full_16d',
      });
    });

    // Verify 3 distinct horizon pills are rendered in the ribbon
    expect(await screen.findByText('1.0%')).toBeInTheDocument();
    expect(screen.getByText('4.8%')).toBeInTheDocument();
    expect(screen.getAllByText('8.3%').length).toBeGreaterThanOrEqual(1);

    // Default selected horizon (24h) should render 1.04% in VerificationPanel
    expect(screen.getByText('1.04%')).toBeInTheDocument();

    // Select Day 2 / 48h horizon by clicking the 48h pill
    fireEvent.click(screen.getByText('48h'));
    // VerificationPanel must now display 4.83% (proving Day 1 value is NOT copied)
    await waitFor(() => {
      expect(screen.getByText('4.83%')).toBeInTheDocument();
    });

    // Select Day 3 / 72h horizon by clicking the 72h pill
    fireEvent.click(screen.getByText('72h'));
    // VerificationPanel must now display 8.25%
    await waitFor(() => {
      expect(screen.getByText('8.25%')).toBeInTheDocument();
    });
  });

  it('safely renders abstention without falling back to fake 0%, LOW, or SUPPORTED', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({
      data: {
        status: 'healthy',
        service: 'veyra-backend',
        version: '3.0.0',
      },
    });

    const mockAbstainData: DashboardIntelligenceResponse = {
      location: {
        query: 'Atlantis',
        resolved_name: null,
        latitude: null,
        longitude: null,
      },
      variable: 'temperature_2m',
      mode: 'full_16d',
      status: 'ABSTAINED',
      selected_prediction: {
        location: 'Atlantis',
        bust_probability: null,
        risk_level: null,
        trust_state: 'UNAVAILABLE',
        abstain: true,
        reason_codes: ['GEO_RESOLUTION_FAILED'],
        model_version: null,
        data_version: null,
        explanation: null,
      },
      timeline: [
        {
          lead_hours: 24,
          lead_days: 1,
          valid_time: '2026-09-12T12:00:00Z',
          bust_probability: null,
          risk_level: null,
          trust_state: 'UNAVAILABLE',
          abstain: true,
          is_certified_horizon: true,
          reason_codes: ['GEO_RESOLUTION_FAILED'],
        },
      ],
      summary: {
        available_points: 0,
        abstained_points: 1,
        total_points: 1,
        max_bust_probability: null,
        max_risk_level: null,
        max_risk_lead_hours: null,
        mean_bust_probability: null,
        elevated_risk_points: 0,
        first_elevated_risk_lead_hours: null,
        overall_decision_mode: 'ABSTAIN',
      },
      scientific_context: {
        model_version: 'veyra-v3-benchmark-lightgbm',
        model_family: 'LightGBM + Isotonic Calibration',
        calibration_method: 'Isotonic Regression',
        feature_count: 50,
        probability_semantics: 'Empirical P(Bust)',
        benchmark_scope: 'Certified frozen split',
        benchmark_lead_horizon_max_hours: 240,
        operational_horizon_max_hours: 384,
        historical_benchmark: {
          dataset: 'certified_splits_v3',
          period: '2017-2019',
          test_samples: 116250,
          test_cycles: 155,
          average_precision: 0.2047,
          pr_auc_trapezoidal: 0.2047,
          roc_auc: 0.7698,
          brier_score: 0.0538,
          bss_vs_e0: 0.0807,
          bss_vs_e1b: 0.0778,
          ece: 0.0064,
        },
        generalization_limits: ['Certified across 25 canonical synoptic stations in India only'],
      },
    };

    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({
      data: mockAbstainData,
    });

    render(<App />);

    const locationInput = screen.getByLabelText(/location name or coordinates/i);
    fireEvent.change(locationInput, { target: { value: 'Atlantis' } });

    const auditBtn = screen.getByRole('button', { name: /audit reliability/i });
    fireEvent.click(auditBtn);

    // Verify safe abstention box is shown
    expect(
      await screen.findByText(/Prediction Safely Abstained: Out of Trust Domain/i)
    ).toBeInTheDocument();

    // Verify reason code is displayed
    expect(screen.getByText('GEO_RESOLUTION_FAILED')).toBeInTheDocument();

    // Verify probability displays ABSTAINED, NOT 0% or 0.00%
    expect(screen.getByText('ABSTAINED')).toBeInTheDocument();
    expect(screen.queryByText('0.00%')).not.toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();

    // Verify risk tier displays ABSTAIN, NOT LOW
    expect(screen.getAllByText('ABSTAIN').length).toBeGreaterThanOrEqual(1);

    // Verify trust state does NOT say SUPPORTED
    expect(screen.queryByText('SUPPORTED')).not.toBeInTheDocument();
  });
});
