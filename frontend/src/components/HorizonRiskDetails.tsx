import React from 'react';
import { HorizonPointResult } from '../api/types';
import { ExplainabilityView } from './ExplainabilityView';
import { AbstentionResult } from './AbstentionResult';

interface HorizonRiskDetailsProps {
  point: HorizonPointResult;
  location: string;
  variable: string;
}

export const HorizonRiskDetails: React.FC<HorizonRiskDetailsProps> = ({
  point,
  location,
  variable,
}) => {
  const { lead_hours, lead_days, valid_time, response, status, error_message } = point;

  if (status === 'ABSTAINED' && response) {
    return (
      <div className="horizon-details-container card glassmorphism">
        <div className="details-header">
          <h3>Selected Horizon: {lead_hours} Hours (Day {lead_days})</h3>
          <span className="valid-time-badge">{new Date(valid_time).toUTCString()}</span>
        </div>
        <AbstentionResult prediction={response} />
      </div>
    );
  }

  if (status === 'ERROR' || !response) {
    return (
      <div className="horizon-details-container card glassmorphism horizon-error-card">
        <div className="details-header">
          <h3>Selected Horizon: {lead_hours} Hours (Day {lead_days})</h3>
          <span className="valid-time-badge">{new Date(valid_time).toUTCString()}</span>
        </div>
        <div className="horizon-error-body">
          <div className="error-icon-shield">⚠️</div>
          <h4>Horizon Evaluation Unavailable</h4>
          <p>{error_message || 'The meteorological ensemble was unavailable for this specific horizon.'}</p>
        </div>
      </div>
    );
  }

  const { bust_probability, risk_level, trust_state, model_version, explanation } = response;
  const percentage =
    bust_probability !== null && bust_probability !== undefined
      ? (bust_probability * 100).toFixed(4)
      : 'N/A';

  return (
    <div className="horizon-details-container card glassmorphism">
      <div className="details-header">
        <div>
          <span className="section-eyebrow">HORIZON DETAIL EVALUATION</span>
          <h3 className="details-title">
            {location} — {lead_hours}h Forecast (Day {lead_days})
          </h3>
        </div>
        <span className="valid-time-badge">
          Valid: <strong>{new Date(valid_time).toUTCString()}</strong>
        </span>
      </div>

      <div className="details-metrics-grid">
        <div className="metric-box probability-box">
          <span className="metric-label">Bust Probability</span>
          <span className="metric-val primary-val">{percentage}%</span>
        </div>

        <div className="metric-box risk-box">
          <span className="metric-label">Risk Category</span>
          <span className={`risk-badge large-badge risk-${risk_level?.toLowerCase()}`}>
            {risk_level || 'UNKNOWN'}
          </span>
        </div>

        <div className="metric-box trust-box">
          <span className="metric-label">Trust State</span>
          <span className={`trust-badge large-badge trust-${trust_state?.toLowerCase()}`}>
            {trust_state || 'UNAVAILABLE'}
          </span>
        </div>

        <div className="metric-box meta-box">
          <span className="metric-label">Model / Variable</span>
          <span className="meta-text">{model_version || 'prototype-gbm-v1'}</span>
          <span className="meta-subtext">{variable}</span>
        </div>
      </div>

      {/* Synchronized Physical Explainability Attribution */}
      {explanation && (
        <div className="details-explanation-section">
          <ExplainabilityView explanation={explanation} />
        </div>
      )}
    </div>
  );
};
