import React from 'react';
import { PredictionResponse, RiskLevel, TrustState } from '../api/types';

interface PredictionResultProps {
  prediction: PredictionResponse;
}

function formatTrustState(trust: TrustState): string {
  switch (trust) {
    case 'HIGH_CONFIDENCE':
      return 'High Confidence';
    case 'MODERATE_CONFIDENCE':
      return 'Moderate Confidence';
    case 'LOW_CONFIDENCE':
      return 'Low Confidence';
    case 'ABSTAINED':
      return 'Abstained';
    case 'UNAVAILABLE':
    default:
      return 'Unavailable';
  }
}

function getRiskClass(risk: RiskLevel | null): string {
  if (!risk) return 'risk-low';
  switch (risk.toUpperCase()) {
    case 'LOW':
      return 'risk-low';
    case 'MEDIUM':
      return 'risk-medium';
    case 'HIGH':
      return 'risk-high';
    case 'CRITICAL':
      return 'risk-critical';
    default:
      return 'risk-low';
  }
}

export const PredictionResult: React.FC<PredictionResultProps> = ({ prediction }) => {
  const { location, bust_probability, risk_level, trust_state, model_version, data_version } = prediction;

  const percentage =
    bust_probability !== null && bust_probability !== undefined
      ? (bust_probability * 100).toFixed(4)
      : 'N/A';

  const riskClass = getRiskClass(risk_level);

  return (
    <section className="hero-prob-card" aria-labelledby="prob-heading" aria-live="polite">
      <div className="prob-metric-title" id="prob-heading">
        Estimated Forecast Bust Probability
      </div>

      <div className={`prob-value-large ${riskClass}`} aria-label={`Bust probability: ${percentage} percent`}>
        {percentage}%
      </div>

      <p className="prob-summary-text">
        Estimated probability that the medium-range weather forecast for{' '}
        <strong style={{ color: 'var(--text-primary)' }}>{location}</strong> will fail unusually badly (exceed historical 95th percentile error).
      </p>

      <div className="meta-badges-row">
        {/* Risk Level Badge */}
        {risk_level && (
          <div className={`risk-badge ${riskClass}`} role="status" aria-label={`Risk level: ${risk_level}`}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>Risk: {risk_level}</span>
          </div>
        )}

        {/* Trust State Badge */}
        <div className="trust-badge" role="status" aria-label={`Model Trust State: ${formatTrustState(trust_state)}`}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span>Trust: {formatTrustState(trust_state)}</span>
        </div>

        {/* Model Identifier Badge */}
        {model_version && (
          <div className="trust-badge" title={`Model version: ${model_version} | Data: ${data_version || 'standard'}`}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            <span>{model_version}</span>
          </div>
        )}
      </div>
    </section>
  );
};
