import React, { useId, useMemo } from 'react';
import { HorizonPointResult, HorizonTimelineResult } from '../api/types';

interface ForecastRiskTimelineProps {
  timeline: HorizonTimelineResult;
  selectedLeadHours: number | null;
  onSelectHorizon: (leadHours: number) => void;
}

export const ForecastRiskTimeline: React.FC<ForecastRiskTimelineProps> = ({
  timeline,
  selectedLeadHours,
  onSelectHorizon,
}) => {
  const chartId = useId();
  const { points, location, variable } = timeline;

  // Chart dimensions & layout parameters
  const svgWidth = 800;
  const svgHeight = 320;
  const margin = { top: 40, right: 40, bottom: 60, left: 65 };
  const innerWidth = svgWidth - margin.left - margin.right;
  const innerHeight = svgHeight - margin.top - margin.bottom;

  // Y-axis fixed honest scale: 0% to 100% (0.0 to 1.0)
  const yMin = 0.0;
  const yMax = 1.0;
  const thresholdValue = 0.28; // 28.0% model decision threshold

  const getY = (val: number) => {
    const clamped = Math.max(yMin, Math.min(yMax, val));
    return innerHeight - ((clamped - yMin) / (yMax - yMin)) * innerHeight;
  };

  const xStep = points.length > 1 ? innerWidth / (points.length - 1) : innerWidth / 2;
  const getX = (index: number) => index * xStep;

  // Compute SVG polyline segments for adjacent successful points (breaking for gaps)
  const lineSegments = useMemo(() => {
    const segments: Array<Array<{ x: number; y: number }>> = [];
    let currentSegment: Array<{ x: number; y: number }> = [];

    points.forEach((point, idx) => {
      if (point.status === 'SUCCESS' && point.response?.bust_probability !== null && point.response?.bust_probability !== undefined) {
        const x = getX(idx);
        const y = getY(point.response.bust_probability);
        currentSegment.push({ x, y });
      } else {
        if (currentSegment.length > 1) {
          segments.push(currentSegment);
        }
        currentSegment = [];
      }
    });

    if (currentSegment.length > 1) {
      segments.push(currentSegment);
    }

    return segments;
  }, [points]);

  const thresholdY = getY(thresholdValue);

  // Keyboard navigation handler
  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === 'ArrowRight' && index < points.length - 1) {
      e.preventDefault();
      onSelectHorizon(points[index + 1].lead_hours);
    } else if (e.key === 'ArrowLeft' && index > 0) {
      e.preventDefault();
      onSelectHorizon(points[index - 1].lead_hours);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelectHorizon(points[index].lead_hours);
    }
  };

  const getRiskColor = (point: HorizonPointResult): string => {
    if (point.status === 'ABSTAINED') return 'var(--color-abstained, #94a3b8)';
    if (point.status === 'ERROR') return 'var(--color-critical, #ef4444)';
    const level = point.response?.risk_level;
    switch (level) {
      case 'LOW':
        return 'var(--color-low-risk, #10b981)';
      case 'MEDIUM':
        return 'var(--color-medium-risk, #f59e0b)';
      case 'HIGH':
        return 'var(--color-high-risk, #f97316)';
      case 'CRITICAL':
        return 'var(--color-critical, #ef4444)';
      default:
        return 'var(--color-low-risk, #10b981)';
    }
  };

  return (
    <div className="forecast-risk-timeline-container card glassmorphism" role="region" aria-label="Visual Forecast Risk Timeline">
      <div className="timeline-header">
        <div>
          <h2 className="timeline-title">Forecast Bust Risk Timeline</h2>
          <p className="timeline-subtitle">
            Probability of forecast failure across lead horizons for <strong>{location}</strong> ({variable})
          </p>
        </div>
        <div className="timeline-badge-stats">
          <span className="stat-pill success-pill">{timeline.successful_count} Valid</span>
          {timeline.abstained_count > 0 && (
            <span className="stat-pill abstained-pill">{timeline.abstained_count} Abstained</span>
          )}
          {timeline.error_count > 0 && (
            <span className="stat-pill error-pill">{timeline.error_count} Unavailable</span>
          )}
        </div>
      </div>

      {/* Primary SVG Multi-Horizon Chart */}
      <div className="svg-chart-wrapper" tabIndex={-1}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="risk-timeline-svg"
          role="img"
          aria-labelledby={`${chartId}-title ${chartId}-desc`}
        >
          <title id={`${chartId}-title`}>Forecast-Bust Risk Curve across Horizons</title>
          <desc id={`${chartId}-desc`}>
            Multi-horizon probability curve showing forecast failure risk from 24h to {points[points.length - 1]?.lead_hours}h for {location}.
          </desc>

          <g transform={`translate(${margin.left}, ${margin.top})`}>
            {/* Background Horizontal Gridlines & Y-Axis Scale Labels */}
            {[0.0, 0.25, 0.5, 0.75, 1.0].map((tick) => {
              const y = getY(tick);
              return (
                <g key={`ytick-${tick}`} className="grid-group">
                  <line
                    x1={0}
                    y1={y}
                    x2={innerWidth}
                    y2={y}
                    className="grid-line"
                    strokeDasharray={tick === 0 ? undefined : '3,3'}
                  />
                  <text x={-12} y={y + 4} className="axis-label-y" textAnchor="end">
                    {(tick * 100).toFixed(0)}%
                  </text>
                </g>
              );
            })}

            {/* Decision Threshold Reference Guideline (0.280) */}
            <g className="threshold-guide-group">
              <line
                x1={0}
                y1={thresholdY}
                x2={innerWidth}
                y2={thresholdY}
                className="threshold-guide-line"
                stroke="var(--color-amber-500, #f59e0b)"
                strokeDasharray="5,4"
                strokeWidth="1.5"
              />
              <text
                x={innerWidth - 6}
                y={thresholdY - 6}
                className="threshold-guide-text"
                textAnchor="end"
                fill="var(--color-amber-400, #fbbf24)"
              >
                0.280 Decision Threshold
              </text>
            </g>

            {/* Straight Line Segments (broken for gaps) */}
            {lineSegments.map((segment, sIdx) => {
              const pointsAttr = segment.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
              return (
                <polyline
                  key={`segment-${sIdx}`}
                  points={pointsAttr}
                  className="timeline-curve-line"
                  fill="none"
                  stroke="var(--accent-primary, #38bdf8)"
                  strokeWidth="3"
                />
              );
            })}

            {/* Interactive Horizon Nodes */}
            {points.map((point, idx) => {
              const x = getX(idx);
              const isSuccess = point.status === 'SUCCESS' && point.response?.bust_probability !== null && point.response?.bust_probability !== undefined;
              const y = isSuccess ? getY(point.response!.bust_probability!) : innerHeight;
              const isSelected = selectedLeadHours === point.lead_hours;
              const nodeColor = getRiskColor(point);

              return (
                <g
                  key={`node-${point.lead_hours}`}
                  className={`horizon-node-group ${isSelected ? 'selected' : ''} ${point.status.toLowerCase()}`}
                  transform={`translate(${x.toFixed(1)}, ${y.toFixed(1)})`}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  aria-label={`${point.lead_hours} hour forecast: ${
                    isSuccess
                      ? `${(point.response!.bust_probability! * 100).toFixed(4)}% probability, Risk: ${point.response!.risk_level}`
                      : point.status === 'ABSTAINED'
                      ? 'Safely Abstained'
                      : 'Unavailable'
                  }`}
                  onClick={() => onSelectHorizon(point.lead_hours)}
                  onKeyDown={(e) => handleKeyDown(e, idx)}
                >
                  {/* Selection Ring */}
                  {isSelected && (
                    <circle
                      r="16"
                      className="node-selection-ring"
                      fill="none"
                      stroke={nodeColor}
                      strokeWidth="2"
                      strokeDasharray="3,2"
                    />
                  )}

                  {/* Outer Node Halo / Shadow */}
                  <circle
                    r={isSelected ? '9' : '7'}
                    className="node-circle"
                    fill={nodeColor}
                    stroke="var(--bg-primary, #0f172a)"
                    strokeWidth="2.5"
                  />

                  {/* Marker symbol for abstained / unavailable */}
                  {point.status === 'ABSTAINED' && (
                    <text y="3" textAnchor="middle" fill="#fff" fontSize="8" fontWeight="bold">
                      ?
                    </text>
                  )}
                  {point.status === 'ERROR' && (
                    <text y="3" textAnchor="middle" fill="#fff" fontSize="8" fontWeight="bold">
                      ✕
                    </text>
                  )}

                  {/* Floating Percentage Tag for Selected Node */}
                  {isSelected && isSuccess && (
                    <g transform="translate(0, -22)" className="node-tooltip-bubble">
                      <rect
                        x="-38"
                        y="-14"
                        width="76"
                        height="20"
                        rx="4"
                        fill="var(--bg-secondary, #1e293b)"
                        stroke={nodeColor}
                        strokeWidth="1"
                      />
                      <text x="0" y="0" textAnchor="middle" fill="#fff" fontSize="11" fontWeight="bold">
                        {(point.response!.bust_probability! * 100).toFixed(2)}%
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* X-Axis Horizon Labels */}
            {points.map((point, idx) => {
              const x = getX(idx);
              const isSelected = selectedLeadHours === point.lead_hours;
              return (
                <g
                  key={`xlabel-${point.lead_hours}`}
                  className={`axis-xlabel-group ${isSelected ? 'selected' : ''}`}
                  transform={`translate(${x.toFixed(1)}, ${innerHeight + 24})`}
                >
                  <text
                    x="0"
                    y="0"
                    textAnchor="middle"
                    className="axis-label-lead"
                    fontWeight={isSelected ? 'bold' : 'normal'}
                    fill={isSelected ? 'var(--accent-primary, #38bdf8)' : 'var(--text-secondary, #94a3b8)'}
                  >
                    {point.lead_hours}h
                  </text>
                  <text x="0" y="14" textAnchor="middle" className="axis-label-day" fontSize="10">
                    D{point.lead_days}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* Risk-Band Horizon Strip */}
      <div className="risk-band-strip" aria-label="Risk category strip by horizon">
        <div className="strip-label">Risk Profile:</div>
        <div className="strip-items-wrapper">
          {points.map((point) => {
            const isSelected = selectedLeadHours === point.lead_hours;
            const level = point.response?.risk_level || point.status;
            return (
              <button
                key={`strip-${point.lead_hours}`}
                type="button"
                className={`strip-item ${level.toLowerCase()} ${isSelected ? 'active' : ''}`}
                onClick={() => onSelectHorizon(point.lead_hours)}
                title={`${point.lead_hours}h Horizon: ${level}`}
                aria-label={`${point.lead_hours}h: ${level}`}
              >
                <span className="strip-hours">{point.lead_hours}h</span>
                <span className="strip-badge">{level}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Semantic Screen-Reader Accessible Fallback Table */}
      <details className="accessible-fallback-details">
        <summary className="accessible-fallback-summary">View Accessible Data Table</summary>
        <div className="accessible-table-scroll">
          <table className="accessible-timeline-table">
            <thead>
              <tr>
                <th scope="col">Horizon</th>
                <th scope="col">Days</th>
                <th scope="col">Valid UTC</th>
                <th scope="col">Bust Probability</th>
                <th scope="col">Risk Level</th>
                <th scope="col">Trust State</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => {
                const prob =
                  p.response?.bust_probability !== null && p.response?.bust_probability !== undefined
                    ? `${(p.response.bust_probability * 100).toFixed(4)}%`
                    : 'N/A';
                return (
                  <tr key={`table-${p.lead_hours}`} className={selectedLeadHours === p.lead_hours ? 'selected-row' : ''}>
                    <td>{p.lead_hours}h</td>
                    <td>D{p.lead_days}</td>
                    <td>{new Date(p.valid_time).toUTCString()}</td>
                    <td>{prob}</td>
                    <td>{p.response?.risk_level || 'N/A'}</td>
                    <td>{p.response?.trust_state || 'N/A'}</td>
                    <td>{p.status}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
};
