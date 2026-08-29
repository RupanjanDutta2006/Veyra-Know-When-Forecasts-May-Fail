import React from 'react';
import { ExplanationItem } from '../api/types';

interface ExplainabilityViewProps {
  explanation: ExplanationItem | null;
}

function formatFactorName(factor: string): string {
  return factor
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatSignal(signal: string): string {
  return signal
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export const ExplainabilityView: React.FC<ExplainabilityViewProps> = ({ explanation }) => {
  if (!explanation) {
    return null;
  }

  const { primary_driver, driver_summary, top_contributing_factors } = explanation;

  return (
    <section className="glass-card" aria-labelledby="explain-heading">
      <h3 id="explain-heading" className="card-title">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--accent-cyan)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
          <line x1="12" y1="22.08" x2="12" y2="12" />
        </svg>
        Physical Explainability & Risk Attribution
      </h3>
      <p className="card-subtitle">
        Deterministic physical attribution derived from ensemble spread, revision drift, and lead horizons.
      </p>

      {/* Primary Driver Narrative Box */}
      <div className="driver-highlight-box">
        <span className="driver-tag">Primary Driver: {formatSignal(primary_driver)}</span>
        <p className="driver-narrative">{driver_summary}</p>
      </div>

      {/* Contributing Factors Grid */}
      {top_contributing_factors && top_contributing_factors.length > 0 && (
        <div>
          <h4
            style={{
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '0.75rem',
            }}
          >
            Key Contributing Signals
          </h4>
          <div className="factors-grid">
            {top_contributing_factors.map((item, index) => (
              <div key={`${item.factor}-${index}`} className="factor-card">
                <div className="factor-name">{formatFactorName(item.factor)}</div>
                <div className="factor-value">
                  {item.value !== null && item.value !== undefined ? item.value : '—'}
                </div>
                <div className="factor-signal">{formatSignal(item.signal)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
