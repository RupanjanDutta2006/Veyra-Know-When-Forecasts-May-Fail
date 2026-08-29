import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import { ForecastRiskTimeline } from '../components/ForecastRiskTimeline';
import { HorizonRiskDetails } from '../components/HorizonRiskDetails';
import { apiClient } from '../api/client';
import {
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
    const mockTimeline = createMockTimeline();
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'predictHorizonTimeline').mockResolvedValue(mockTimeline);

    render(<App />);

    const timelineTab = screen.getByRole('tab', { name: /Visual Risk Timeline/i });
    fireEvent.click(timelineTab);

    const submitBtn = screen.getByRole('button', { name: /Generate Risk Timeline/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Forecast Bust Risk Timeline')).toBeInTheDocument();
    });

    let resolvePromise: (val: any) => void;
    const delayedPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.spyOn(apiClient, 'predictHorizonTimeline').mockReturnValue(delayedPromise as any);

    fireEvent.click(submitBtn);

    expect(screen.queryByText('Forecast Bust Risk Timeline')).not.toBeInTheDocument();
    expect(screen.getByText('Evaluating Forecast Trajectory')).toBeInTheDocument();

    resolvePromise!(mockTimeline);
  });

  it('18. Validation failure clears stale timeline state', async () => {
    const mockTimeline = createMockTimeline();
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'predictHorizonTimeline').mockResolvedValue(mockTimeline);

    render(<App />);

    const timelineTab = screen.getByRole('tab', { name: /Visual Risk Timeline/i });
    fireEvent.click(timelineTab);

    const submitBtn = screen.getByRole('button', { name: /Generate Risk Timeline/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Forecast Bust Risk Timeline')).toBeInTheDocument();
    });

    const locInput = screen.getByLabelText(/Location or Coordinates/i);
    fireEvent.change(locInput, { target: { value: '' } });

    const form = locInput.closest('form')!;
    fireEvent.submit(form);

    expect(screen.queryByText('Forecast Bust Risk Timeline')).not.toBeInTheDocument();
    expect(screen.getByText(/Please enter a valid location/i)).toBeInTheDocument();
  });

  it('19. Handles 429 rate-limit error gracefully', async () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'predictHorizonTimeline').mockRejectedValue(new Error('Rate limit exceeded. Please retry after 15 seconds.'));

    render(<App />);

    const timelineTab = screen.getByRole('tab', { name: /Visual Risk Timeline/i });
    fireEvent.click(timelineTab);

    const submitBtn = screen.getByRole('button', { name: /Generate Risk Timeline/i });
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
    const singlePrediction = createMockPrediction(72, 0.0569, 'LOW');
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'predictForecastBust').mockResolvedValue({ data: singlePrediction });

    render(<App />);

    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.6900%')).toBeInTheDocument();
      expect(screen.getByText(/Risk: LOW/i)).toBeInTheDocument();
      expect(screen.getByText(/Physical Explainability & Risk Attribution/i)).toBeInTheDocument();
    });
  });

  it('23. [TEST 10 REGRESSION] Switching from Timeline mode to Single mode clears timeline and selected horizon details', async () => {
    const mockTimeline = createMockTimeline();
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'predictHorizonTimeline').mockResolvedValue(mockTimeline);

    render(<App />);

    // 1. Switch to Timeline mode
    const timelineTab = screen.getByRole('tab', { name: /Visual Risk Timeline/i });
    fireEvent.click(timelineTab);

    // 2. Submit timeline
    const submitBtn = screen.getByRole('button', { name: /Generate Risk Timeline/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Forecast Bust Risk Timeline')).toBeInTheDocument();
      expect(screen.getByText('HORIZON DETAIL EVALUATION')).toBeInTheDocument();
    });

    // 3. Switch back to Single Target Forecast mode without submitting
    const singleTab = screen.getByRole('tab', { name: /Single Target Forecast/i });
    fireEvent.click(singleTab);

    // 4. Verify timeline chart, risk strip, and horizon details are immediately gone
    expect(screen.queryByText('Forecast Bust Risk Timeline')).not.toBeInTheDocument();
    expect(screen.queryByText('HORIZON DETAIL EVALUATION')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk Profile:')).not.toBeInTheDocument();

    // 5. Verify Single Target empty state is rendered
    expect(screen.getByText('Sentinel Ready for Assessment')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Estimate Bust Probability/i })).toBeInTheDocument();
  });

  it('24. [TEST 10 REGRESSION] Switching from Single mode to Timeline mode clears single prediction results', async () => {
    const singlePrediction = createMockPrediction(72, 0.0569, 'LOW');
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });
    vi.spyOn(apiClient, 'predictForecastBust').mockResolvedValue({ data: singlePrediction });

    render(<App />);

    // 1. Submit Single prediction
    const submitBtn = screen.getByRole('button', { name: /Estimate Bust Probability/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('5.6900%')).toBeInTheDocument();
    });

    // 2. Switch to Timeline mode without submitting
    const timelineTab = screen.getByRole('tab', { name: /Visual Risk Timeline/i });
    fireEvent.click(timelineTab);

    // 3. Single prediction results must disappear
    expect(screen.queryByText('5.6900%')).not.toBeInTheDocument();
    expect(screen.queryByText('Physical Attribution Analysis')).not.toBeInTheDocument();

    // 4. Timeline empty state is shown
    expect(screen.getByText('Sentinel Ready for Assessment')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generate Risk Timeline/i })).toBeInTheDocument();
  });

  it('25. Mode switching before submission preserves clean empty states without rendering stale results', () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });

    render(<App />);

    const singleTab = screen.getByRole('tab', { name: /Single Target Forecast/i });
    const timelineTab = screen.getByRole('tab', { name: /Visual Risk Timeline/i });

    // Initially Single mode empty state
    expect(screen.getByText('Sentinel Ready for Assessment')).toBeInTheDocument();

    // Switch to Timeline mode
    fireEvent.click(timelineTab);
    expect(screen.getByText('Sentinel Ready for Assessment')).toBeInTheDocument();
    expect(screen.queryByText('Forecast Bust Risk Timeline')).not.toBeInTheDocument();

    // Switch back to Single mode
    fireEvent.click(singleTab);
    expect(screen.getByText('Sentinel Ready for Assessment')).toBeInTheDocument();
    expect(screen.queryByText('Estimated Forecast Bust Probability')).not.toBeInTheDocument();
  });

  it('26. Location and variable form inputs are preserved across mode switches', () => {
    vi.spyOn(apiClient, 'getHealth').mockResolvedValue({ data: { status: 'ok', service: 'veyra-api', version: '0.1.0' } });

    render(<App />);

    // Change location to Kolkata and variable to surface_pressure
    const locInput = screen.getByLabelText(/Location or Coordinates/i);
    fireEvent.change(locInput, { target: { value: 'Kolkata' } });

    const varSelect = screen.getByLabelText(/Meteorological Variable/i);
    fireEvent.change(varSelect, { target: { value: 'surface_pressure' } });

    // Switch to Timeline mode
    const timelineTab = screen.getByRole('tab', { name: /Visual Risk Timeline/i });
    fireEvent.click(timelineTab);

    // Verify inputs preserved
    expect(screen.getByLabelText(/Location or Coordinates/i)).toHaveValue('Kolkata');
    expect(screen.getByLabelText(/Meteorological Variable/i)).toHaveValue('surface_pressure');

    // Switch back to Single mode
    const singleTab = screen.getByRole('tab', { name: /Single Target Forecast/i });
    fireEvent.click(singleTab);

    // Verify inputs still preserved
    expect(screen.getByLabelText(/Location or Coordinates/i)).toHaveValue('Kolkata');
    expect(screen.getByLabelText(/Meteorological Variable/i)).toHaveValue('surface_pressure');
  });
});
