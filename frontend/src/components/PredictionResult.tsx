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
  const {
    location,
    bust_probability,
    risk_level,
    trust_state,
    model_version,
    data_version,
    confidence_index,
    uncertainty_pct,
  } = prediction;

  const percentage =
    bust_probability !== null && bust_probability !== undefined
      ? (bust_probability * 100).toFixed(4)
      : 'N/A';

  const riskClass = getRiskClass(risk_level);

  return (
    <section className="hero-prob-card" aria-labelledby="prob-heading" aria-live="polite">
      <div
        className="prob-metric-title"
        id="prob-heading"
        title="Estimated calibrated probability that forecast error meets or exceeds the stratum-specific bust threshold derived from historical Train reforecasts (2000-2013)."
      >
        Calibrated Bust Probability
      </div>

      <div className={`prob-value-large ${riskClass}`} aria-label={`Bust probability: ${percentage} percent`}>
        {percentage}%
      </div>

      <p className="prob-summary-text">
        Estimated calibrated probability that the forecast for{' '}
        <strong style={{ color: 'var(--text-primary)' }}>{location}</strong> will meet or exceed the historical 95th percentile error threshold for this station, variable, and lead-horizon bin.
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
        <div
          className="trust-badge"
          role="status"
          aria-label={`Model Trust State: ${formatTrustState(trust_state)}`}
          title="Operational Trust: Nominal Pipeline Integrity (valid location, QC passed, model loaded)"
        >
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

        {/* Heuristic Decision Certainty Badge */}
        {confidence_index !== null && confidence_index !== undefined && (
          <div className="trust-badge" title="Probability Separation Score: 2*|P - 0.5| (heuristic distance from boundary ambiguity; not a formal statistical confidence interval)">
            <span>Certainty: {(confidence_index * 100).toFixed(1)}%</span>
          </div>
        )}

        {/* Boundary Ambiguity Badge */}
        {uncertainty_pct !== null && uncertainty_pct !== undefined && (
          <div className="trust-badge" title="Decision Boundary Ambiguity: proximity to 0.5 threshold (not a formal predictive uncertainty interval)">
            <span>Ambiguity: {uncertainty_pct.toFixed(1)}%</span>
          </div>
        )}

        {/* Scientific Certification Badge */}
        {prediction.certification && (
          <div
            className={`trust-badge cert-badge ${
              prediction.certification.certification_status === 'CERTIFIED'
                ? 'cert-certified'
                : prediction.certification.certification_status === 'OUTSIDE_CERTIFIED_SCOPE'
                ? 'cert-outside'
                : 'cert-unknown'
            }`}
            role="status"
            aria-label={`Scientific Certification: ${prediction.certification.certification_status}`}
            title={`Scientific Certification (${prediction.certification.certification_policy_version}): ${prediction.certification.certification_reason}`}
            style={{
              borderColor:
                prediction.certification.certification_status === 'CERTIFIED'
                  ? '#10b981'
                  : prediction.certification.certification_status === 'OUTSIDE_CERTIFIED_SCOPE'
                  ? '#f59e0b'
                  : '#ef4444',
              color:
                prediction.certification.certification_status === 'CERTIFIED'
                  ? '#059669'
                  : prediction.certification.certification_status === 'OUTSIDE_CERTIFIED_SCOPE'
                  ? '#d97706'
                  : '#dc2626',
              fontWeight: 600,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
            <span>
              {prediction.certification.certification_status === 'CERTIFIED'
                ? 'CERTIFIED EVIDENCE SCOPE'
                : prediction.certification.certification_status === 'OUTSIDE_CERTIFIED_SCOPE'
                ? 'OUTSIDE CERTIFIED EVIDENCE SCOPE'
                : 'CERTIFICATION UNKNOWN'}
            </span>
          </div>
        )}

        {/* OOD Diagnostic Badge (Gate C2) */}
        {prediction.ood_diagnostics && (
          <div
            className="trust-badge ood-badge"
            role="status"
            aria-label={`Distribution Diagnostic: ${prediction.ood_diagnostics.status}`}
            title={`Physical Domain Diagnostic (${prediction.ood_diagnostics.policy_version}): ${prediction.ood_diagnostics.reason_detail} (diagnostic only; does not affect calibration or certification)`}
            style={{
              borderColor:
                prediction.ood_diagnostics.status === 'IN_DISTRIBUTION'
                  ? '#10b981'
                  : prediction.ood_diagnostics.status === 'OUT_OF_DISTRIBUTION'
                  ? '#f59e0b'
                  : '#6b7280',
              color:
                prediction.ood_diagnostics.status === 'IN_DISTRIBUTION'
                  ? '#059669'
                  : prediction.ood_diagnostics.status === 'OUT_OF_DISTRIBUTION'
                  ? '#d97706'
                  : '#6b7280',
              fontWeight: 500,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            </svg>
            <span>
              {prediction.ood_diagnostics.status === 'IN_DISTRIBUTION'
                ? 'IN DISTRIBUTION'
                : prediction.ood_diagnostics.status === 'OUT_OF_DISTRIBUTION'
                ? 'OUT OF DISTRIBUTION'
                : 'OOD UNKNOWN'}
            </span>
          </div>
        )}
      </div>
    </section>
  );
};

