import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { DashboardTimelinePoint } from '../api/types';
import { TrendingUp, Award, ShieldAlert } from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface TimelineChartProps {
  timeline: DashboardTimelinePoint[];
  selectedLeadHours: number | null;
  onSelectHorizon: (leadHours: number) => void;
  variable: string;
}

export const TimelineChart: React.FC<TimelineChartProps> = ({
  timeline,
  selectedLeadHours,
  onSelectHorizon,
  variable,
}) => {
  if (!timeline || timeline.length === 0) {
    return null;
  }

  // Labels: e.g. "24h (D1)", "48h (D2)", etc.
  const labels = timeline.map((p) => `${p.lead_hours}h (D${p.lead_days.toFixed(0)})`);

  // Data values: null for abstained/unavailable points so Chart.js breaks the line cleanly
  const probData = timeline.map((p) =>
    p.bust_probability !== null && !p.abstain ? Number(p.bust_probability.toFixed(4)) : null
  );

  // Point background colors based on risk tier and certification
  const pointColors = timeline.map((p) => {
    if (p.abstain || p.bust_probability === null) return '#94a3b8'; // gray for abstained
    if (p.bust_probability >= 0.75) return '#991b1b'; // CRITICAL
    if (p.bust_probability >= 0.50) return '#cd2026'; // HIGH
    if (p.bust_probability >= 0.20) return '#b87a00'; // MEDIUM
    return '#2e8540'; // LOW
  });

  const pointRadii = timeline.map((p) =>
    p.lead_hours === selectedLeadHours ? 7 : 4
  );

  const chartData = {
    labels,
    datasets: [
      {
        label: `Calibrated P(Bust) — ${variable}`,
        data: probData,
        borderColor: '#0071bc',
        backgroundColor: 'rgba(0, 113, 188, 0.08)',
        borderWidth: 2.5,
        pointBackgroundColor: pointColors,
        pointBorderColor: '#ffffff',
        pointBorderWidth: 1.5,
        pointRadius: pointRadii,
        pointHoverRadius: 8,
        tension: 0.2,
        fill: true,
        spanGaps: false, // Strict null safety: NEVER connect across missing / abstained data
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (_event: any, elements: any[]) => {
      if (elements && elements.length > 0) {
        const index = elements[0].index;
        const target = timeline[index];
        if (target) {
          onSelectHorizon(target.lead_hours);
        }
      }
    },
    layout: { padding: { top: 8, bottom: 4, left: 4, right: 12 } },
    scales: {
      y: {
        min: 0.0,
        max: 1.0,
        ticks: {
          stepSize: 0.2,
          color: '#1f2937',
          font: { size: 10, weight: 'bold' as const },
          callback: (val: any) => `${(Number(val) * 100).toFixed(0)}%`,
        },
        grid: { color: '#e5e7eb' },
        title: {
          display: true,
          text: 'Bust Probability',
          color: '#4b5563',
          font: { size: 10, weight: 'bold' as const },
        },
      },
      x: {
        ticks: {
          maxRotation: 45,
          color: '#1f2937',
          font: { size: 9, weight: 'bold' as const },
        },
        grid: { color: '#f3f4f6' },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context: any) => {
            const point = timeline[context.dataIndex];
            if (point.abstain || point.bust_probability === null) {
              return `P(Bust): ABSTAINED (${point.reason_codes?.join(', ') || 'Out of Domain'})`;
            }
            const certText = point.is_certified_horizon ? 'Certified Benchmark' : 'Operational Only';
            return [
              `P(Bust): ${(point.bust_probability * 100).toFixed(2)}% [Risk: ${point.risk_level}]`,
              `Scope: ${certText}`,
              `Valid: ${point.valid_time}`,
            ];
          },
        },
      },
    },
  };

  return (
    <div className="timeline-chart-panel" role="region" aria-label="Forecast Bust Risk Timeline">
      <div className="timeline-chart-header">
        <span className="timeline-chart-title">
          <TrendingUp size={16} /> FORECAST BUST RISK TIMELINE ({variable.toUpperCase()})
        </span>
        <div className="timeline-chart-legend">
          <span className="legend-badge badge-certified" title="Covered by Day 23 frozen benchmark certification (2017-2019)">
            <Award size={12} /> &le;240h Certified Scope
          </span>
          <span className="legend-badge badge-operational" title="Operational numerical extension (uncertified by benchmark)">
            <ShieldAlert size={12} /> &gt;240h Operational Scope
          </span>
        </div>
      </div>

      <div className="timeline-canvas-wrap">
        <Line data={chartData} options={options} />
      </div>

      {/* Interactive Horizon Cards Ribbon */}
      <div className="horizon-ribbon" role="tablist" aria-label="Selectable Forecast Horizons">
        {timeline.map((point) => {
          const isSelected = point.lead_hours === selectedLeadHours;
          const isAbstain = point.abstain || point.bust_probability === null;
          const probStr = !isAbstain ? `${(point.bust_probability! * 100).toFixed(1)}%` : 'ABSTAIN';

          let probColor = '#64748b';
          if (!isAbstain) {
            if (point.bust_probability! >= 0.75) probColor = 'var(--risk-crit)';
            else if (point.bust_probability! >= 0.50) probColor = 'var(--risk-high)';
            else if (point.bust_probability! >= 0.20) probColor = 'var(--risk-med)';
            else probColor = 'var(--risk-low)';
          }

          return (
            <button
              key={point.lead_hours}
              type="button"
              role="tab"
              aria-selected={isSelected}
              className={`horizon-pill ${isSelected ? 'active' : ''}`}
              onClick={() => onSelectHorizon(point.lead_hours)}
              title={`${point.lead_hours}h: ${probStr} | ${point.is_certified_horizon ? 'Certified Benchmark' : 'Operational Extension'}`}
            >
              <div className="horizon-pill-lead">{point.lead_hours}h</div>
              <div className="horizon-pill-prob" style={{ color: isSelected ? '#ffffff' : probColor }}>
                {probStr}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default TimelineChart;
