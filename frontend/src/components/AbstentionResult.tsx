import React from 'react';
import { PredictionResponse } from '../api/types';

interface AbstentionResultProps {
  prediction: PredictionResponse;
}

function formatReasonCode(code: string): string {
  switch (code) {
    case 'INVALID_LOCATION':
      return 'Unresolvable Location / Coordinates';
    case 'DATA_UNAVAILABLE':
      return 'Forecast Ensemble Data Unavailable';
    case 'QC_FAILED':
      return 'Meteorological Quality Control Failed';
    case 'OOD_ABSTAIN':
    case 'OOD_DETECTED':
      return 'Out-of-Distribution Atmospheric State';
    case 'MODEL_NOT_READY':
    case 'MODEL_UNAVAILABLE':
      return 'Predictive Model Offline / Unready';
    case 'INSUFFICIENT_DATA':
      return 'Insufficient Ensemble Members';
    case 'EXTREME_VOLATILITY':
      return 'Extreme Atmospheric Volatility';
    default:
      return code.replace(/_/g, ' ');
  }
}

export const AbstentionResult: React.FC<AbstentionResultProps> = ({ prediction }) => {
  const { location, reason_codes } = prediction;

  return (
    <section className="abstain-card" aria-labelledby="abstain-heading" aria-live="polite">
      <div className="abstain-icon-circle" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
        </svg>
      </div>

      <h3 id="abstain-heading" className="abstain-title">
        Prediction Safely Abstained
      </h3>

      <p className="abstain-desc">
        Veyra cannot issue a verified forecast bust assessment for{' '}
        <strong style={{ color: '#ffffff' }}>{location || 'the requested target'}</strong> due to safety guardrails.
        This is a safe abstention, <em style={{ fontStyle: 'normal', color: '#fca5a5' }}>not a low-risk prediction</em>.
      </p>

      <div className="reason-pill-list" aria-label="Abstention Reason Codes">
        {reason_codes && reason_codes.length > 0 ? (
          reason_codes.map((code) => (
            <span key={code} className="reason-pill">
              {formatReasonCode(code)}
            </span>
          ))
        ) : (
          <span className="reason-pill">Unspecified Safety Abstention</span>
        )}
      </div>
    </section>
  );
};
