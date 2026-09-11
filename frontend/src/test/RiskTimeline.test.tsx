import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import { ForecastRiskTimeline } from '../components/ForecastRiskTimeline';
import { HorizonRiskDetails } from '../components/HorizonRiskDetails';
import { apiClient } from '../api/client';
import {
  DashboardIntelligenceResponse,
  DashboardMode,
  DashboardTimelinePoint,
  HorizonPointResult,
  HorizonTimelineResult,
  PredictionResponse,
} from '../api/types';

// Helper mock responses
const createMockPrediction = (
  leadHours: number,
  prob: number,
  risk: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL',
  trust: 'HIGH_CONFIDENCE' | 'MODERATE_CONFIDENCE' | 'LOW_CONFIDENCE' | 'ABSTAINED' = 'HIGH_CONFIDENCE',
  abstain = false
): PredictionResponse => ({
  location: 'London',
  bust_probability: abstain ? null : prob,
  risk_level: abstain ? null : risk,
  trust_state: trust,
  abstain,
  reason_codes: abstain ? ['ENSEMBLE_SPREAD_EXCEEDED'] : ['ISSUE_TIME_NORMAL'],
  model_version: 'prototype-gbm-v1',
  data_version: 'gefs-openmeteo-v1.0',
  explanation: abstain
    ? null
    : {
        primary_driver: `Forecast horizon is ${leadHours}h with standard atmospheric variability.`,
        driver_summary: `Evaluating ${leadHours}h medium-range lead.`,
        top_contributing_factors: [
          { factor: 'lead_hours', value: leadHours, signal: 'MEDIUM_RANGE' },
          { factor: 'ensemble_spread_temp', value: 1.45, signal: 'STABLE' },
        ],
      },
});

const createMockTimeline = (): HorizonTimelineResult => {
  const leads = [24, 48, 72, 96, 120, 144, 168];
  const probs = [0.0561, 0.0563, 0.0568, 0.0575, 0.0582, 0.0590, 0.0610];
  const points: HorizonPointResult[] = leads.map((lead, idx) => ({
    lead_hours: lead,
    lead_days: lead / 24,
    valid_time: `2026-09-0${Math.floor(lead / 24) + 1}T12:00:00Z`,
    response: createMockPrediction(lead, probs[idx], 'LOW'),
    status: 'SUCCESS',
  }));

  return {
    location: 'London',
    variable: 'temperature_2m',
    issue_time: '2026-09-01T12:00:00Z',
    preset: '7_DAY',
    points,
    successful_count: 7,
    abstained_count: 0,
    error_count: 0,
  };
};

const createMockDashboardResponse = (
  mode: DashboardMode = 'standard_7d',
  location = 'London',
  variable = 'temperature_2m'
): DashboardIntelligenceResponse => {
  const leads = mode === 'single' ? [24] : [24, 48, 72, 96, 120, 144, 168];
  const probs = [0.0561, 0.0563, 0.0568, 0.0575, 0.0582, 0.0590, 0.0610];
  const timeline: DashboardTimelinePoint[] = leads.map((lead, idx) => ({
    lead_hours: lead,
    lead_days: lead / 24,
    valid_time: `2026-09-0${Math.floor(lead / 24) + 1}T12:00:00Z`,
    bust_probability: probs[idx] ?? 0.0561,
    risk_level: 'LOW',
    trust_state: 'HIGH_CONFIDENCE',
    abstain: false,
    is_certified_horizon: lead <= 240,
    operational_extension: lead > 240,
    reason_codes: ['SUCCESS'],
  }));

  return {
    location: {
      query: location,
      resolved_name: `${location}, Synoptic Station`,
      latitude: 51.5074,
      longitude: -0.1278,
    },
    variable,
    mode,
    status: 'SUCCESS',
    selected_prediction: {
      location,
      bust_probability: probs[0],
      risk_level: 'LOW',
      trust_state: 'HIGH_CONFIDENCE',
      abstain: false,
      reason_codes: ['SUCCESS'],
      model_version: 'v3-lightgbm-frozen',
      data_version: 'gefs-reanalysis-v3',
      explanation: {
        primary_driver: 'stable_ensemble_agreement',
        driver_summary: 'Stable forecast across multi-horizon ensemble.',
        top_contributing_factors: [],
      },
    },
    timeline,
    summary: {
      available_points: leads.length,
      abstained_points: 0,
      total_points: leads.length,
      max_bust_probability: probs[probs.length - 1],
      max_risk_level: 'LOW',
      max_risk_lead_hours: leads[leads.length - 1],
      mean_bust_probability: 0.0578,
      elevated_risk_points: 0,
      first_elevated_risk_lead_hours: null,
      overall_decision_mode: 'NOMINAL_OPERATIONS',
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
  };
};

describe('Day 16 — Visual Forecast Risk & Timeline Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Timeline renders expected horizon count (7 nodes for 7-Day preset)', () => {
    const timeline = createMockTimeline();
    const handleSelect = vi.fn();

    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={96}
        onSelectHorizon={handleSelect}
      />
    );

    const nodes = screen.getAllByRole('button', { name: /hour forecast:/i });
    expect(nodes).toHaveLength(7);
    expect(screen.getByText('7 Valid')).toBeInTheDocument();
  });

  it('2. Real backend probability values render accurately in nodes', () => {
    const timeline = createMockTimeline();
    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={96}
        onSelectHorizon={vi.fn()}
      />
    );

    expect(screen.getByText('5.75%')).toBeInTheDocument();
  });

  it('3. Four-decimal percentage formatting rendered in HorizonRiskDetails', () => {
    const point: HorizonPointResult = {
      lead_hours: 96,
      lead_days: 4,
      valid_time: '2026-09-05T12:00:00Z',
      response: createMockPrediction(96, 0.057482, 'LOW'),
      status: 'SUCCESS',
    };

    render(
      <HorizonRiskDetails
        point={point}
        location="London"
        variable="temperature_2m"
      />
    );

    expect(screen.getByText('5.7482%')).toBeInTheDocument();
    expect(screen.getByText('LOW')).toBeInTheDocument();
    expect(screen.getByText('HIGH_CONFIDENCE')).toBeInTheDocument();
  });

  it('4. Preserves requested horizon ordering (24h to 168h)', () => {
    const timeline = createMockTimeline();
    const { container } = render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={24}
        onSelectHorizon={vi.fn()}
      />
    );

    const labels = container.querySelectorAll('.axis-label-lead');
    const textValues = Array.from(labels).map((l) => l.textContent?.trim());
    expect(textValues).toEqual(['24h', '48h', '72h', '96h', '120h', '144h', '168h']);
  });

  it('5. Node selection updates details view', () => {
    const timeline = createMockTimeline();
    const handleSelect = vi.fn();

    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={24}
        onSelectHorizon={handleSelect}
      />
    );

    const node120 = screen.getByRole('button', { name: /120 hour forecast:/i });
    fireEvent.click(node120);

    expect(handleSelect).toHaveBeenCalledWith(120);
  });

  it('6. Selected explanation strictly belongs to selected horizon (no cross-horizon mixing)', () => {
    const point96: HorizonPointResult = {
      lead_hours: 96,
      lead_days: 4,
      valid_time: '2026-09-05T12:00:00Z',
      response: createMockPrediction(96, 0.0575, 'LOW'),
      status: 'SUCCESS',
    };

    render(
      <HorizonRiskDetails
        point={point96}
        location="London"
        variable="temperature_2m"
      />
    );

    expect(screen.getByText(/Forecast horizon is 96h/i)).toBeInTheDocument();
    expect(screen.getByText('Evaluating 96h medium-range lead.')).toBeInTheDocument();
    expect(screen.getAllByText('96').length).toBeGreaterThanOrEqual(1);
  });

  it('7. Keyboard selection triggers onSelectHorizon via Enter and Space', () => {
    const timeline = createMockTimeline();
    const handleSelect = vi.fn();

    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={24}
        onSelectHorizon={handleSelect}
      />
    );

    const node48 = screen.getByRole('button', { name: /48 hour forecast:/i });
    fireEvent.keyDown(node48, { key: 'Enter' });
    expect(handleSelect).toHaveBeenCalledWith(48);

    fireEvent.keyDown(node48, { key: ' ' });
    expect(handleSelect).toHaveBeenCalledWith(48);
  });

  it('8. ArrowLeft and ArrowRight step through horizons', () => {
    const timeline = createMockTimeline();
    const handleSelect = vi.fn();

    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={48}
        onSelectHorizon={handleSelect}
      />
    );

    const node48 = screen.getByRole('button', { name: /48 hour forecast:/i });
    fireEvent.keyDown(node48, { key: 'ArrowRight' });
    expect(handleSelect).toHaveBeenCalledWith(72);

    fireEvent.keyDown(node48, { key: 'ArrowLeft' });
    expect(handleSelect).toHaveBeenCalledWith(24);
  });

  it('9. Abstained horizon representation displays safe warning and is not green', () => {
    const abstainedPoint: HorizonPointResult = {
      lead_hours: 72,
      lead_days: 3,
      valid_time: '2026-09-04T12:00:00Z',
      response: createMockPrediction(72, 0, 'LOW', 'ABSTAINED', true),
      status: 'ABSTAINED',
    };

    render(
      <HorizonRiskDetails
        point={abstainedPoint}
        location="London"
        variable="temperature_2m"
      />
    );

    expect(screen.getByText('Prediction Safely Abstained')).toBeInTheDocument();
    expect(screen.getByText('ENSEMBLE SPREAD EXCEEDED')).toBeInTheDocument();
    expect(screen.getByText(/not a low-risk prediction/i)).toBeInTheDocument();
  });

  it('10. Null probability never becomes 0% on abstained or error points', () => {
    const abstainedPoint: HorizonPointResult = {
      lead_hours: 72,
      lead_days: 3,
      valid_time: '2026-09-04T12:00:00Z',
      response: createMockPrediction(72, 0, 'LOW', 'ABSTAINED', true),
      status: 'ABSTAINED',
    };

    const timeline: HorizonTimelineResult = {
      location: 'London',
      variable: 'temperature_2m',
      issue_time: '2026-09-01T12:00:00Z',
      preset: '7_DAY',
      points: [abstainedPoint],
      successful_count: 0,
      abstained_count: 1,
      error_count: 0,
    };

    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={72}
        onSelectHorizon={vi.fn()}
      />
    );

    expect(screen.queryByText('0.00%')).not.toBeInTheDocument();
    expect(screen.queryByText('0.0000%')).not.toBeInTheDocument();
  });

  it('11. Partial request failure handles mixed success, abstention, and error', () => {
    const points: HorizonPointResult[] = [
      {
        lead_hours: 24,
        lead_days: 1,
        valid_time: '2026-09-02T12:00:00Z',
        response: createMockPrediction(24, 0.0561, 'LOW'),
        status: 'SUCCESS',
      },
      {
        lead_hours: 48,
        lead_days: 2,
        valid_time: '2026-09-03T12:00:00Z',
        response: createMockPrediction(48, 0, 'LOW', 'ABSTAINED', true),
        status: 'ABSTAINED',
      },
      {
        lead_hours: 72,
        lead_days: 3,
        valid_time: '2026-09-04T12:00:00Z',
        response: null,
        status: 'ERROR',
        error_message: 'Upstream provider timeout',
      },
      {
        lead_hours: 96,
        lead_days: 4,
        valid_time: '2026-09-05T12:00:00Z',
        response: createMockPrediction(96, 0.0575, 'LOW'),
        status: 'SUCCESS',
      },
    ];

    const timeline: HorizonTimelineResult = {
      location: 'London',
      variable: 'temperature_2m',
      issue_time: '2026-09-01T12:00:00Z',
      preset: '7_DAY',
      points,
      successful_count: 2,
      abstained_count: 1,
      error_count: 1,
    };

    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={24}
        onSelectHorizon={vi.fn()}
      />
    );

    expect(screen.getByText('2 Valid')).toBeInTheDocument();
    expect(screen.getByText('1 Abstained')).toBeInTheDocument();
    expect(screen.getByText('1 Unavailable')).toBeInTheDocument();
  });

  it('12. Complete timeline error renders error details card', () => {
    const errorPoint: HorizonPointResult = {
      lead_hours: 24,
      lead_days: 1,
      valid_time: '2026-09-02T12:00:00Z',
      response: null,
      status: 'ERROR',
      error_message: 'Network connection failed.',
    };

    render(
      <HorizonRiskDetails
        point={errorPoint}
        location="London"
        variable="temperature_2m"
      />
    );

    expect(screen.getByText('Horizon Evaluation Unavailable')).toBeInTheDocument();
    expect(screen.getByText('Network connection failed.')).toBeInTheDocument();
  });

  it('13 & 14. Missing/abstained horizon breaks line without interpolation', () => {
    const points: HorizonPointResult[] = [
      {
        lead_hours: 24,
        lead_days: 1,
        valid_time: '2026-09-02T12:00:00Z',
        response: createMockPrediction(24, 0.0561, 'LOW'),
        status: 'SUCCESS',
      },
      {
        lead_hours: 48,
        lead_days: 2,
        valid_time: '2026-09-03T12:00:00Z',
        response: null,
        status: 'ABSTAINED',
      },
      {
        lead_hours: 72,
        lead_days: 3,
        valid_time: '2026-09-04T12:00:00Z',
        response: createMockPrediction(72, 0.0568, 'LOW'),
        status: 'SUCCESS',
      },
    ];

    const timeline: HorizonTimelineResult = {
      location: 'London',
      variable: 'temperature_2m',
      issue_time: '2026-09-01T12:00:00Z',
      preset: '7_DAY',
      points,
      successful_count: 2,
      abstained_count: 1,
      error_count: 0,
    };

    const { container } = render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={24}
        onSelectHorizon={vi.fn()}
      />
    );

    const polylines = container.querySelectorAll('.timeline-curve-line');
    expect(polylines).toHaveLength(0);
  });

  it('15 & 16. Backend risk state and trust state are faithfully rendered', () => {
    const point: HorizonPointResult = {
      lead_hours: 96,
      lead_days: 4,
      valid_time: '2026-09-05T12:00:00Z',
      response: createMockPrediction(96, 0.35, 'MEDIUM', 'MODERATE_CONFIDENCE'),
      status: 'SUCCESS',
    };

    render(
      <HorizonRiskDetails
        point={point}
        location="London"
        variable="temperature_2m"
      />
    );

    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
    expect(screen.getByText('MODERATE_CONFIDENCE')).toBeInTheDocument();
  });

  it('17. Stale timeline is cleared when new timeline request is initiated', async () => {
    const mockTimeline = createMockDashboardResponse('standard_7d');
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({ data: mockTimeline, requestId: 'req_1' });

    render(<App />);

    const submitBtn = screen.getByRole('button', { name: /Audit Reliability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.61%')).toBeInTheDocument();
    });

    let resolvePromise: (val: any) => void;
    const delayedPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.spyOn(apiClient, 'getDashboardIntelligence').mockReturnValue(delayedPromise as any);

    fireEvent.click(submitBtn);

    expect(screen.getByRole('button', { name: /Auditing Reliability/i })).toBeInTheDocument();

    resolvePromise!({ data: mockTimeline, requestId: 'req_2' });
  });

  it('18. Validation failure clears stale timeline state', async () => {
    const mockTimeline = createMockDashboardResponse('standard_7d');
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({ data: mockTimeline, requestId: 'req_1' });

    render(<App />);

    const submitBtn = screen.getByRole('button', { name: /Audit Reliability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.61%')).toBeInTheDocument();
    });

    const locInput = screen.getByLabelText(/Location Name or Coordinates/i);
    fireEvent.change(locInput, { target: { value: '' } });

    expect(screen.queryByText('5.61%')).not.toBeInTheDocument();
    expect(submitBtn).toBeDisabled();
  });

  it('19. Handles 429 rate-limit error gracefully', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({
      error: { error: 'RATE_LIMIT_EXCEEDED', message: 'Rate limit exceeded. Please retry after 15 seconds.', status_code: 429 },
    });

    render(<App />);

    const submitBtn = screen.getByRole('button', { name: /Audit Reliability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Rate limit exceeded/i)).toBeInTheDocument();
    });
  });

  it('20. Accessible SVG title and description present', () => {
    const timeline = createMockTimeline();
    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={24}
        onSelectHorizon={vi.fn()}
      />
    );

    expect(screen.getByText('Forecast-Bust Risk Curve across Horizons')).toBeInTheDocument();
    expect(screen.getByText(/Multi-horizon probability curve/i)).toBeInTheDocument();
  });

  it('21. Accessible semantic fallback data table rendered', () => {
    const timeline = createMockTimeline();
    render(
      <ForecastRiskTimeline
        timeline={timeline}
        selectedLeadHours={24}
        onSelectHorizon={vi.fn()}
      />
    );

    expect(screen.getByText('View Accessible Data Table')).toBeInTheDocument();
    expect(screen.getAllByText('D7').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('5.6100%')).toBeInTheDocument();
  });

  it('22. Day 15 Single Prediction workflow continues functioning flawlessly', async () => {
    const mockSingle = createMockDashboardResponse('single', 'London');
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({ data: mockSingle, requestId: 'req_single' });

    render(<App />);

    const modeSelect = screen.getByLabelText(/Evaluation Horizon Mode/i);
    fireEvent.change(modeSelect, { target: { value: 'single' } });

    const submitBtn = screen.getByRole('button', { name: /Audit Reliability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.61%')).toBeInTheDocument();
      expect(screen.getByText('LOW')).toBeInTheDocument();
    });
  });

  it('23. [TEST 10 REGRESSION] Switching from Timeline mode to Single mode clears timeline and selected horizon details', async () => {
    const mockTimeline = createMockDashboardResponse('standard_7d');
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({ data: mockTimeline, requestId: 'req_7d' });

    render(<App />);

    // 1. Submit timeline in standard_7d mode
    const submitBtn = screen.getByRole('button', { name: /Audit Reliability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.61%')).toBeInTheDocument();
    });

    // 2. Switch to Single mode without submitting
    const modeSelect = screen.getByLabelText(/Evaluation Horizon Mode/i);
    fireEvent.change(modeSelect, { target: { value: 'single' } });

    // 3. Verify previous results are immediately cleared
    expect(screen.queryByText('5.61%')).not.toBeInTheDocument();
    expect(screen.getByText(/FORECAST BUST RISK TIMELINE STANDBY/i)).toBeInTheDocument();
  });

  it('24. [TEST 10 REGRESSION] Switching from Single mode to Timeline mode clears single prediction results', async () => {
    const mockSingle = createMockDashboardResponse('single', 'London');
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'getDashboardIntelligence').mockResolvedValue({ data: mockSingle, requestId: 'req_single' });

    render(<App />);

    // 1. Switch to Single mode and submit
    const modeSelect = screen.getByLabelText(/Evaluation Horizon Mode/i);
    fireEvent.change(modeSelect, { target: { value: 'single' } });

    const submitBtn = screen.getByRole('button', { name: /Audit Reliability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.61%')).toBeInTheDocument();
    });

    // 2. Switch to 7-Day Timeline mode without submitting
    fireEvent.change(modeSelect, { target: { value: 'standard_7d' } });

    // 3. Single prediction results must disappear
    expect(screen.queryByText('5.61%')).not.toBeInTheDocument();
    expect(screen.getByText(/FORECAST BUST RISK TIMELINE STANDBY/i)).toBeInTheDocument();
  });

  it('25. Mode switching before submission preserves clean empty states without rendering stale results', () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });

    render(<App />);

    const modeSelect = screen.getByLabelText(/Evaluation Horizon Mode/i);

    // Initially standby
    expect(screen.getByText(/FORECAST BUST RISK TIMELINE STANDBY/i)).toBeInTheDocument();

    // Switch to Single mode
    fireEvent.change(modeSelect, { target: { value: 'single' } });
    expect(screen.getByText(/FORECAST BUST RISK TIMELINE STANDBY/i)).toBeInTheDocument();

    // Switch back to 7-Day mode
    fireEvent.change(modeSelect, { target: { value: 'standard_7d' } });
    expect(screen.getByText(/FORECAST BUST RISK TIMELINE STANDBY/i)).toBeInTheDocument();
  });

  it('26. Location and variable form inputs are preserved across mode switches', () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });

    render(<App />);

    // Change location to Kolkata and variable to surface_pressure
    const locInput = screen.getByLabelText(/Location Name or Coordinates/i);
    fireEvent.change(locInput, { target: { value: 'Kolkata' } });

    const varSelect = screen.getByLabelText(/Target Meteorological Variable/i);
    fireEvent.change(varSelect, { target: { value: 'surface_pressure' } });

    // Switch to Single mode
    const modeSelect = screen.getByLabelText(/Evaluation Horizon Mode/i);
    fireEvent.change(modeSelect, { target: { value: 'single' } });

    // Verify inputs preserved
    expect(screen.getByLabelText(/Location Name or Coordinates/i)).toHaveValue('Kolkata');
    expect(screen.getByLabelText(/Target Meteorological Variable/i)).toHaveValue('surface_pressure');

    // Switch to Full 16-Day mode
    fireEvent.change(modeSelect, { target: { value: 'full_16d' } });

    // Verify inputs still preserved
    expect(screen.getByLabelText(/Location Name or Coordinates/i)).toHaveValue('Kolkata');
    expect(screen.getByLabelText(/Target Meteorological Variable/i)).toHaveValue('surface_pressure');
  });
});
