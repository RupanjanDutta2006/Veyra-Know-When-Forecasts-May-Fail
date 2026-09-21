import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Award,
  Info,
  Flame,
} from 'lucide-react';
import {
  DashboardScientificContext,
  DashboardSummary,
  DashboardTimelinePoint,
  PredictionResponse,
} from '../api/types';

interface VerificationPanelProps {
  prediction: PredictionResponse | null;
  selectedPoint?: DashboardTimelinePoint | null;
  summary?: DashboardSummary | null;
  scientificContext?: DashboardScientificContext | null;
  locationQuery: string;
  variable: string;
}

export const VerificationPanel: React.FC<VerificationPanelProps> = ({
  prediction,
  selectedPoint,
  summary,
  scientificContext,
  locationQuery,
  variable,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'explainability' | 'conformal' | 'evidence'>('overview');

  // Active point evaluation context (either selected timeline point or base prediction)
  const isAbstain = Boolean(
    (selectedPoint && (selectedPoint.abstain || selectedPoint.bust_probability === null)) ||
    (!selectedPoint && prediction && (prediction.abstain || prediction.bust_probability === null)) ||
    (!selectedPoint && !prediction)
  );

  const activeProb = selectedPoint
    ? selectedPoint.bust_probability
    : prediction
    ? prediction.bust_probability
    : null;

  const probDisplay =
    activeProb !== null && activeProb !== undefined
      ? `${(activeProb * 100).toFixed(2)}%`
      : 'ABSTAINED';

  const riskLevel = selectedPoint
    ? selectedPoint.risk_level || (isAbstain ? 'ABSTAIN' : 'LOW')
    : prediction
    ? prediction.risk_level || (isAbstain ? 'ABSTAIN' : 'LOW')
    : 'ABSTAIN';

  const trustState = selectedPoint
    ? selectedPoint.trust_state
    : prediction
    ? prediction.trust_state
    : 'UNAVAILABLE';

  const reasonCodes = selectedPoint
    ? selectedPoint.reason_codes
    : prediction
    ? prediction.reason_codes
    : ['STANDBY'];

  const confidenceIndex =
    prediction?.confidence_index !== null && prediction?.confidence_index !== undefined
      ? `${(prediction.confidence_index * 100).toFixed(0)}%`
      : activeProb !== null
      ? `${(Math.abs(activeProb - 0.5) * 200).toFixed(0)}%`
      : 'N/A';

  const uncertaintyPct =
    prediction?.uncertainty_pct !== null && prediction?.uncertainty_pct !== undefined
      ? `±${prediction.uncertainty_pct.toFixed(1)}%`
      : activeProb !== null
      ? `±${((1 - Math.abs(activeProb - 0.5) * 2) * 100).toFixed(1)}%`
      : 'N/A';

  const stabilityScore = prediction?.stability_index ?? 92;

  const failureFingerprint =
    typeof prediction?.failure_fingerprint === 'string'
      ? prediction.failure_fingerprint
      : prediction?.failure_fingerprint?.label ||
        prediction?.failure_fingerprint?.group ||
        (isAbstain ? 'OUT_OF_DOMAIN_OR_VOLATILE' : 'STABLE_SYNOPTIC_CONSENSUS');

  const explanation = prediction?.explanation;
  const leadHours = selectedPoint ? selectedPoint.lead_hours : 24;
  const isBenchmarkLead = selectedPoint ? selectedPoint.is_certified_horizon : (leadHours <= 240);

  const rawCertStatus = prediction?.certification?.certification_status;
  const effectiveCertStatus = !isBenchmarkLead
    ? 'OUTSIDE_CERTIFIED_SCOPE'
    : rawCertStatus || (isAbstain ? 'OUTSIDE_CERTIFIED_SCOPE' : 'CERTIFICATION_UNKNOWN');

  const effectiveCertReason = !isBenchmarkLead
    ? `Lead horizon ${leadHours}h exceeds maximum certified benchmark horizon (240h).`
    : prediction?.certification?.certification_reason ||
      (effectiveCertStatus === 'CERTIFIED'
        ? 'Request lies within frozen benchmark evidence boundary.'
        : 'Location or variable lies outside frozen benchmark evidence boundary.');

  const getRiskColor = (risk: string | null) => {
    switch (risk) {
      case 'CRITICAL': return 'var(--risk-crit)';
      case 'HIGH': return 'var(--risk-high)';
      case 'MEDIUM': return 'var(--risk-med)';
      case 'LOW': return 'var(--risk-low)';
      default: return 'var(--trust-abstain)';
    }
  };

  return (
    <aside className="panel verification-panel" aria-label="Forecast Bust Verification Telemetry">
      <div className="panel-header">
        <span className="panel-title">
          <Activity size={16} /> Conformal Telemetry
        </span>
        <span className="panel-badge">
          {leadHours}h Horizon &bull; {isBenchmarkLead ? 'Within Frozen Benchmark Lead Scope (\u2264240h)' : 'Extended Operational Horizon (>240h)'}
        </span>
      </div>

      {/* Scientific Certification Evidence Status */}
      <div
        className="cert-scope-banner"
        title={effectiveCertReason}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          borderRadius: '6px',
          marginBottom: '12px',
          background: effectiveCertStatus === 'CERTIFIED' ? '#ecfdf5' : '#fffbeb',
          border: `1px solid ${effectiveCertStatus === 'CERTIFIED' ? '#a7f3d0' : '#fde68a'}`,
          color: effectiveCertStatus === 'CERTIFIED' ? '#065f46' : '#92400e',
          fontSize: '0.8rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
          <Award size={15} color={effectiveCertStatus === 'CERTIFIED' ? '#059669' : '#d97706'} />
          <span>Scientific Certification:</span>
          <span
            className="diag-pill"
            style={{
              background: effectiveCertStatus === 'CERTIFIED' ? '#dcfce7' : '#fef3c7',
              color: effectiveCertStatus === 'CERTIFIED' ? '#15803d' : '#b45309',
              fontWeight: 700,
              fontSize: '0.75rem',
            }}
          >
            {effectiveCertStatus === 'CERTIFIED'
              ? 'CERTIFIED'
              : effectiveCertStatus === 'OUTSIDE_CERTIFIED_SCOPE'
              ? 'OUTSIDE CERTIFIED SCOPE'
              : 'CERTIFICATION UNKNOWN'}
          </span>
        </div>
        <span style={{ fontSize: '0.75rem', color: effectiveCertStatus === 'CERTIFIED' ? '#047857' : '#78350f' }}>
          {effectiveCertStatus === 'CERTIFIED' ? '25-Station Evidence Scope' : 'Outside Benchmark Scope'}
        </span>
      </div>

      {/* Summary Banner (Aggregated intelligence across requested timeline) */}
      {summary && (
        <div className="summary-banner" role="region" aria-label="Summary Peak Risk Intelligence">
          <div className="summary-metric">
            <span className="summary-metric-label">Peak P(Bust)</span>
            <span className="summary-metric-value">
              {summary.max_bust_probability !== null ? `${(summary.max_bust_probability * 100).toFixed(1)}%` : 'N/A'}
            </span>
          </div>
          <div className="summary-metric">
            <span className="summary-metric-label">Peak Risk Level</span>
            <span className="summary-metric-value" style={{ color: getRiskColor(summary.max_risk_level) }}>
              {summary.max_risk_level || 'N/A'}
            </span>
          </div>
          <div className="summary-metric">
            <span className="summary-metric-label">Peak Horizon</span>
            <span className="summary-metric-value">
              {summary.max_risk_lead_hours !== null ? `${summary.max_risk_lead_hours}h` : 'N/A'}
            </span>
          </div>
          <div className="summary-metric">
            <span className="summary-metric-label">Elevated Horizons</span>
            <span className="summary-metric-value">
              {summary.elevated_risk_points} / {summary.total_points}
            </span>
          </div>
        </div>
      )}

      {/* Abstention Banner (shown when model abstains or location is unresolvable) */}
      {isAbstain && (
        <div className="abstention-box" role="alert">
          <div className="abstention-title">
            <AlertTriangle size={18} /> Prediction Safely Abstained: Out of Trust Domain
          </div>
          <div className="abstention-desc">
            Veyra cannot issue a verified forecast bust assessment for{' '}
            <strong>{locationQuery || 'the requested target'}</strong> due to safety guardrails.
            This is a <em>safe abstention</em>, <strong>not a low-risk prediction</strong>.
          </div>
          <div className="reason-pill-list">
            {reasonCodes.map((code) => (
              <span key={code} className="reason-pill">
                {code}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Operational Decision Guidance */}
      {prediction?.decision_guidance && (
        <div
          style={{
            background: '#e0f2fe',
            border: '1px solid #7dd3fc',
            borderRadius: '6px',
            padding: '8px 12px',
            fontSize: '0.8rem',
            color: '#0369a1',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Info size={16} style={{ flexShrink: 0 }} />
          <span>{prediction.decision_guidance}</span>
        </div>
      )}

      {/* Failure Fingerprint Card */}
      <div className="fingerprint-card">
        <div>
          <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', fontWeight: 700, color: '#166534' }}>
            Failure Fingerprint
          </div>
          <div style={{ fontFamily: 'JetBrains Mono', fontWeight: 700, color: '#15803d', fontSize: '0.85rem' }}>
            {failureFingerprint}
          </div>
        </div>
        <span
          className="diag-pill"
          style={{
            background: isAbstain ? '#fee2e2' : '#dcfce7',
            color: isAbstain ? '#991b1b' : '#166534',
          }}
        >
          {isAbstain ? 'ABSTAIN' : 'CONSENSUS'}
        </span>
      </div>

      {/* Navigation Tabs */}
      <div className="panel-tabs">
        <button
          type="button"
          className={activeTab === 'overview' ? 'active' : ''}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          type="button"
          className={activeTab === 'explainability' ? 'active' : ''}
          onClick={() => setActiveTab('explainability')}
        >
          Explainability
        </button>
        <button
          type="button"
          className={activeTab === 'conformal' ? 'active' : ''}
          onClick={() => setActiveTab('conformal')}
        >
          Calibration
        </button>
        <button
          type="button"
          className={activeTab === 'evidence' ? 'active' : ''}
          onClick={() => setActiveTab('evidence')}
        >
          Scientific Provenance
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <>
          <div className="kpi-matrix">
            <div className="kpi-card">
              <div className="kpi-title">Bust Probability</div>
              <div
                className="kpi-val"
                style={{
                  color: isAbstain ? 'var(--trust-abstain)' : getRiskColor(riskLevel),
                }}
              >
                {probDisplay}
              </div>
              <div className="kpi-sub">{variable}</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Risk Tier</div>
              <div
                className="kpi-val"
                style={{
                  fontSize: '1.05rem',
                  color: isAbstain ? 'var(--trust-abstain)' : getRiskColor(riskLevel),
                }}
              >
                {riskLevel}
              </div>
              <div className="kpi-sub">
                {isAbstain ? 'Safety Guardrail' : riskLevel === 'CRITICAL' ? 'Immediate Action' : riskLevel === 'HIGH' ? 'Elevated Caution' : 'Nominal'}
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Decision Boundary Confidence</div>
              <div className="kpi-val" style={{ color: 'var(--trust-normal)' }}>
                {confidenceIndex}
              </div>
              <div className="kpi-sub">Separation index</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Stability Index</div>
              <div className="kpi-val" style={{ color: 'var(--noaa-blue)' }}>
                {stabilityScore}/100
              </div>
              <div className="kpi-sub">Trajectory spread</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Uncertainty %</div>
              <div className="kpi-val">{uncertaintyPct}</div>
              <div className="kpi-sub">Boundary proximity</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Trust State</div>
              <div
                className="kpi-val"
                style={{
                  fontSize: trustState.length > 12 ? '0.78rem' : '0.92rem',
                  color: isAbstain ? 'var(--trust-abstain)' : 'var(--trust-normal)',
                }}
              >
                {trustState.replace(/_/g, ' ')}
              </div>
              <div className="kpi-sub">Pipeline integrity</div>
            </div>
          </div>

          {/* Dominant Risk Drivers */}
          {prediction?.dominant_risk_drivers && prediction.dominant_risk_drivers.length > 0 && (
            <div style={{ marginTop: '12px' }}>
              <div className="kpi-title" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Flame size={12} style={{ color: '#ea580c' }} /> Dominant Risk Drivers
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
                {prediction.dominant_risk_drivers.map((driver, idx) => (
                  <span
                    key={idx}
                    style={{
                      background: '#f1f5f9',
                      color: '#334155',
                      border: '1px solid #cbd5e1',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontFamily: 'JetBrains Mono',
                    }}
                  >
                    {driver}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Explainability Tab */}
      {activeTab === 'explainability' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {explanation ? (
            <>
              <div
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  padding: '12px',
                }}
              >
                <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700, color: '#64748b' }}>
                  Primary Synoptic Driver
                </div>
                <div style={{ fontWeight: 700, color: 'var(--noaa-dark-blue)', marginTop: '2px' }}>
                  {explanation.primary_driver.replace(/_/g, ' ').toUpperCase()}
                </div>
                <p style={{ fontSize: '0.85rem', color: '#334155', marginTop: '6px', lineHeight: 1.4 }}>
                  {explanation.driver_summary}
                </p>
              </div>

              {explanation.top_contributing_factors && explanation.top_contributing_factors.length > 0 && (
                <div>
                  <div className="kpi-title" style={{ marginBottom: '6px' }}>
                    Physical Factor Attributions
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {explanation.top_contributing_factors.map((factor, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '8px 10px',
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: '4px',
                          fontSize: '0.8rem',
                        }}
                      >
                        <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 600 }}>
                          {factor.factor}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontFamily: 'JetBrains Mono', color: '#64748b' }}>
                            {factor.value !== null ? factor.value.toFixed(2) : '--'}
                          </span>
                          <span
                            className="diag-pill"
                            style={{
                              background: factor.signal.includes('HIGH') ? '#fee2e2' : '#f1f5f9',
                              color: factor.signal.includes('HIGH') ? '#991b1b' : '#475569',
                            }}
                          >
                            {factor.signal}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: '20px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
              Physical explainability attribution unavailable for abstained or unready predictions.
            </div>
          )}
        </div>
      )}

      {/* Conformal Range / Calibration Tab */}
      {activeTab === 'conformal' && (
        <div className="conformal-bar-container">
          <div style={{ marginBottom: '12px' }}>
            <div className="kpi-title">Operational Risk Tier Boundaries</div>
            <div style={{ fontSize: '0.8rem', color: '#334155', marginTop: '4px', lineHeight: 1.5 }}>
              <div>&bull; <strong>LOW Risk:</strong> P(Bust) &lt; 0.20</div>
              <div>&bull; <strong>MEDIUM Risk:</strong> 0.20 &le; P(Bust) &lt; 0.50</div>
              <div>&bull; <strong>HIGH Risk:</strong> 0.50 &le; P(Bust) &lt; 0.75</div>
              <div>&bull; <strong>CRITICAL Risk:</strong> P(Bust) &ge; 0.75</div>
            </div>
          </div>

          <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '10px' }}>
            <div className="kpi-title">Calibration &amp; Governance</div>
            <div style={{ fontSize: '0.8rem', color: '#475569', marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div>Calibration Method: <strong>{scientificContext?.calibration_method || 'Isotonic Regression'}</strong></div>
              <div>Decision Mode: <strong>{prediction?.decision_mode || selectedPoint?.decision_mode || 'STANDARD_MONITORING'}</strong></div>
              <div>Operational Trust Horizon: <strong>{prediction?.operational_trust_horizon_hours || 168}h limit</strong></div>
              <div>Benchmark Lead Scope: <strong>&le; {scientificContext?.benchmark_lead_horizon_max_hours || 240}h (Day 23 Certified)</strong></div>
            </div>
          </div>
        </div>
      )}

      {/* Scientific Provenance Tab */}
      {activeTab === 'evidence' && (
        <div className="evidence-box">
{`[VEYRA SCIENTIFIC PROVENANCE]
ACTIVE MODEL: ${scientificContext?.model_version || prediction?.model_version || 'veyra-v3-benchmark-lightgbm'}
MODEL FAMILY: ${scientificContext?.model_family || 'LightGBM + Isotonic Calibration'}
FEATURE CONTRACT: ${scientificContext?.feature_count || 50} Canonical Engineered Features
DATA PIPELINE: ${prediction?.data_version || 'openmeteo-gefs-v1.0'}
PROBABILITY SEMANTICS:
${scientificContext?.probability_semantics || 'Calibrated empirical probability of forecast absolute error meeting or exceeding the stratum-specific bust threshold under certified Day 22 label definitions.'}

[FROZEN HISTORICAL CHAMPIONSHIP BENCHMARK (DAY 23)]
TEST PARTITION: 2017-01-01 to 2019-12-31 (Strict Chronological Holdout)
TEST SAMPLES: ${scientificContext?.historical_benchmark?.test_samples || 116250}
TEST FORECAST CYCLES: ${scientificContext?.historical_benchmark?.test_cycles || 155}
BRIER SCORE: ${scientificContext?.historical_benchmark?.brier_score || 0.053798} (Calibrated)
EXPECTED CALIBRATION ERROR (ECE): ${scientificContext?.historical_benchmark?.ece || 0.0064} (< 1%)
ROC-AUC: ${scientificContext?.historical_benchmark?.roc_auc || 0.7698}
PR-AUC (AVERAGE PRECISION): ${scientificContext?.historical_benchmark?.average_precision || 0.2047}
BRIER SKILL SCORE VS CLIMATOLOGY (E0): ${scientificContext?.historical_benchmark?.bss_vs_e0 || 0.0807}
BRIER SKILL SCORE VS ENSEMBLE SPREAD (E1b): ${scientificContext?.historical_benchmark?.bss_vs_e1b || 0.0778}

[GENERALIZATION BOUNDARIES]
${(scientificContext?.generalization_limits || [
  'Certified across 25 canonical synoptic stations in India only',
  'Certified for 3 target variables: temperature_2m, wind_speed_10m, surface_pressure',
  'Certified across 10 benchmark lead horizons (24h to 240h); horizons >240h (264h-384h) are operational only',
  'Certified on historical Test partition (2017-2019)',
  'Model estimates empirical forecast-bust probability, NOT severe weather or disaster risk',
]).map((lim) => `• ${lim}`).join('\n')}`}
        </div>
      )}
    </aside>
  );
};

export default VerificationPanel;
