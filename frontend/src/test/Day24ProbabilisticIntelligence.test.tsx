import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PredictionResult } from '../components/PredictionResult';
import { ForecastRiskTimeline } from '../components/ForecastRiskTimeline';
import { ModelEvaluationView } from '../components/ModelEvaluationView';
import { apiClient } from '../api/client';
import { PredictionResponse, HorizonTimelineResult, V3ModelEvaluationResponse } from '../api/types';

describe('Day 24 Probabilistic Intelligence UI Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockPrediction: PredictionResponse = {
    location: 'Denver',
    bust_probability: 0.35,
    risk_level: 'MEDIUM',
    trust_state: 'HIGH_CONFIDENCE',
    abstain: false,
    reason_codes: ['NOMINAL'],
    calibration_status: 'CALIBRATED',
    model_version: 'v3-lightgbm-isotonic',
    data_version: 'canonical-v3',
    explanation: null,
    confidence_index: 0.70,
    uncertainty_pct: 30.0,
    ood_score: 0.0,
    decision_mode: 'ACTIVE_PREDICTION',
  };

  it('renders "Calibrated Bust Probability" card title', () => {
    render(<PredictionResult prediction={mockPrediction} />);
    expect(screen.getByText('Calibrated Bust Probability')).toBeInTheDocument();
  });

  it('renders heuristic certainty and ambiguity labels with operational trust', () => {
    render(<PredictionResult prediction={mockPrediction} />);
    expect(screen.getByTitle(/Probability Separation Score/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Decision Boundary Ambiguity/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Nominal Pipeline Integrity/i)).toBeInTheDocument();
    expect(screen.getByText(/Certainty:\s*70\.0%/i)).toBeInTheDocument();
    expect(screen.getByText(/Ambiguity:\s*30\.0%/i)).toBeInTheDocument();
  });

  it('renders "Reference Alert Guideline 28%" on the timeline with explanatory tooltip', () => {
    const mockTimeline: HorizonTimelineResult = {
      location: 'Denver',
      variable: 'temperature_2m',
      issue_time: '2026-09-10T00:00:00Z',
      preset: '7_DAY',
      successful_count: 1,
      abstained_count: 0,
      error_count: 0,
      points: [
        {
          lead_hours: 24,
          lead_days: 1.0,
          valid_time: '2026-09-11T00:00:00Z',
          status: 'SUCCESS',
          response: mockPrediction,
        },
      ],
    };

    render(
      <ForecastRiskTimeline
        timeline={mockTimeline}
        selectedLeadHours={24}
        onSelectHorizon={() => {}}
      />
    );

    expect(screen.getByText(/Reference Alert Guideline 28%/i)).toBeInTheDocument();
  });

  it('renders ModelEvaluationView diagnostics panel with frozen benchmark metrics and caveats', async () => {
    const mockV3Eval: V3ModelEvaluationResponse = {
      model_name: 'Veyra Forecast Bust Model V3 (Challenger Champion)',
      model_version: 'v3-lightgbm-isotonic',
      model_family: 'LightGBM Gradient Boosted Trees (Isotonic Calibrated)',
      feature_count: 50,
      calibration_method: 'isotonic',
      evaluation_dataset: 'NOAA GEFS Historical Canonical Split (2017-2019)',
      evaluation_split: 'test',
      evaluation_period: '2017-2019',
      test_samples: 116250,
      test_cycles: 155,
      benchmark_scope: '25 canonical stations x 3 meteorological variables x 10 lead horizons (24-240h)',
      evaluation_status: 'FROZEN_CHAMPION',
      metrics: {
        average_precision: 0.2047,
        pr_auc_trapezoidal: 0.2124,
        roc_auc: 0.7698,
        brier_score: 0.053798,
        bss_vs_e0: 0.0807,
        bss_vs_e1b: 0.0778,
        ece: 0.0064,
      },
      provenance: { source: 'Day 23 Retraining Decision Synthesis & Evaluation Audit' },
      generalization_limits: [
        'Evaluated across 25 canonical stations; unseen stations uncertified.',
        'Historical N=5 ensemble; live N=31 operational equivalence uncertified.',
      ],
    };

    vi.spyOn(apiClient, 'getV3Evaluation').mockResolvedValue({ data: mockV3Eval });

    render(<ModelEvaluationView />);

    // Toggle button should be visible
    const toggleBtn = screen.getByRole('button', { name: /Model Evaluation & Scientific Diagnostics/i });
    expect(toggleBtn).toBeInTheDocument();

    // Click to expand
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(screen.getByText('0.2047')).toBeInTheDocument();
      expect(screen.getByText('0.2124')).toBeInTheDocument();
      expect(screen.getByText('0.7698')).toBeInTheDocument();
      expect(screen.getByText('0.053798')).toBeInTheDocument();
      expect(screen.getByText('+0.0807')).toBeInTheDocument();
      expect(screen.getByText('+0.0778')).toBeInTheDocument();
      expect(screen.getByText('0.0064')).toBeInTheDocument();
      expect(screen.getAllByText(/Frozen Historical Benchmark/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/116,250/i)).toBeInTheDocument();
      expect(screen.getByText(/unseen stations uncertified/i)).toBeInTheDocument();
    });
  });
});
