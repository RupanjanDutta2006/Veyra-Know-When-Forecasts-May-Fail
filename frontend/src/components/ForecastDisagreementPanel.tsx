import React, { useState, useEffect } from 'react';
import {
  GitCompare,
  Activity,
  AlertOctagon,
  RefreshCw,
  ExternalLink,
  HelpCircle,
} from 'lucide-react';
import { apiClient } from '../api/client';
import {
  ForecastDisagreementResponse,
  RiskLevel,
} from '../api/types';

interface ForecastDisagreementPanelProps {
  initialLocation?: string;
  initialVariable?: string;
  initialLeadHours?: number;
  onNavigateToSpatial?: () => void;
  onNavigateToMultiLocation?: () => void;
}

const PRESET_STATIONS = ['Kolkata', 'Delhi', 'Mumbai', 'Chennai', 'Bengaluru'];

const VARIABLE_OPTIONS = [
  { value: 'temperature_2m', label: '2m Temperature (°C)', unit: '°C' },
  { value: 'wind_speed_10m', label: '10m Wind Speed (m/s)', unit: 'm/s' },
  { value: 'surface_pressure', label: 'Surface Pressure (hPa)', unit: 'hPa' },
];

const HORIZON_OPTIONS = [
  { lead: 24, label: '24h (1 Day)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 48, label: '48h (2 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 72, label: '72h (3 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 96, label: '96h (4 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 120, label: '120h (5 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 144, label: '144h (6 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 168, label: '168h (7 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 192, label: '192h (8 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 216, label: '216h (9 Days)', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 240, label: '240h (10 Days) [Benchmark Limit]', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 264, label: '264h (11 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 288, label: '288h (12 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 312, label: '312h (13 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 336, label: '336h (14 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 360, label: '360h (15 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 384, label: '384h (16 Days) [Max Operational Horizon]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
];

export const ForecastDisagreementPanel: React.FC<ForecastDisagreementPanelProps> = ({
  initialLocation = 'Kolkata',
  initialVariable = 'temperature_2m',
  initialLeadHours = 24,
  onNavigateToSpatial,
  onNavigateToMultiLocation,
}) => {
  const [location, setLocation] = useState<string>(initialLocation);
  const [variable, setVariable] = useState<string>(initialVariable);
  const [leadHours, setLeadHours] = useState<number>(initialLeadHours);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [disagreementData, setDisagreementData] = useState<ForecastDisagreementResponse | null>(null);

  // Sync initial props if updated externally
  useEffect(() => {
    if (initialLocation) setLocation(initialLocation);
  }, [initialLocation]);

  useEffect(() => {
    if (initialVariable) setVariable(initialVariable);
  }, [initialVariable]);

  useEffect(() => {
    if (initialLeadHours) setLeadHours(initialLeadHours);
  }, [initialLeadHours]);

  const isCertifiedScope = leadHours <= 240;

  const handleFetchDisagreement = async (locToUse = location, varToUse = variable, leadToUse = leadHours) => {
    if (!locToUse.trim()) {
      setError('Please provide a target location.');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const { data, error: apiError } = await apiClient.getForecastDisagreement({
        location: locToUse.trim(),
        variable: varToUse,
        lead_hours: leadToUse,
      });

      if (apiError) {
        setError(apiError.message || apiError.error || 'Disagreement diagnostics evaluation failed.');
        setDisagreementData(null);
      } else if (data) {
        setDisagreementData(data);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unexpected communication error.');
      setDisagreementData(null);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    handleFetchDisagreement(initialLocation, initialVariable, initialLeadHours);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getRiskBadgeColor = (risk: RiskLevel | null) => {
    switch (risk) {
      case 'CRITICAL':
        return { bg: '#fee2e2', text: '#991b1b', border: '#f87171' };
      case 'HIGH':
        return { bg: '#ffedd5', text: '#9a3412', border: '#fb923c' };
      case 'MEDIUM':
        return { bg: '#fef3c7', text: '#92400e', border: '#fcd34d' };
      case 'LOW':
        return { bg: '#dcfce7', text: '#166534', border: '#86efac' };
      default:
        return { bg: '#f1f5f9', text: '#475569', border: '#cbd5e1' };
    }
  };

  const riskColors = getRiskBadgeColor(disagreementData?.risk_level || null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '20px 24px', maxWidth: '1440px', margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
      {/* Header Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, #0b2545 0%, #133c55 60%, #1d4e89 100%)',
          color: '#ffffff',
          borderRadius: '12px',
          padding: '24px 28px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <GitCompare size={26} color="#38bdf8" />
              <h1 style={{ margin: 0, fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.01em' }}>
                FORECAST DISAGREEMENT INTELLIGENCE
              </h1>
              <span
                style={{
                  background: '#6366f1',
                  color: '#ffffff',
                  padding: '3px 10px',
                  borderRadius: '20px',
                  fontSize: '0.75rem',
                  fontWeight: 800,
                  letterSpacing: '0.04em',
                }}
              >
                DAY 29
              </span>
              <span
                style={{
                  background: 'rgba(255, 255, 255, 0.15)',
                  color: '#ffffff',
                  padding: '3px 10px',
                  borderRadius: '20px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                }}
              >
                NOAA GEFS • 31 Members
              </span>
            </div>
            <p style={{ margin: '6px 0 0 0', opacity: 0.9, fontSize: '0.88rem', maxWidth: '850px', lineHeight: 1.4 }}>
              Diagnostic analysis of numerical member dispersion and observed ensemble spread across medium-range horizons.
              Disagreement reflects internal evidence variance and is strictly distinguished from calibrated bust probability P(BUST).
            </p>
          </div>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {onNavigateToMultiLocation && (
              <button
                type="button"
                onClick={onNavigateToMultiLocation}
                style={{
                  background: 'rgba(255, 255, 255, 0.12)',
                  border: '1px solid rgba(255, 255, 255, 0.25)',
                  color: '#ffffff',
                  borderRadius: '6px',
                  padding: '8px 14px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                Multi-Location View (Day 28) <ExternalLink size={13} />
              </button>
            )}
            {onNavigateToSpatial && (
              <button
                type="button"
                onClick={onNavigateToSpatial}
                style={{
                  background: 'rgba(255, 255, 255, 0.12)',
                  border: '1px solid rgba(255, 255, 255, 0.25)',
                  color: '#ffffff',
                  borderRadius: '6px',
                  padding: '8px 14px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                Spatial Map (Day 27) <ExternalLink size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Scientific Lead Scope Banner */}
        <div
          style={{
            marginTop: '4px',
            padding: '8px 14px',
            borderRadius: '6px',
            background: isCertifiedScope ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.25)',
            border: isCertifiedScope ? '1px solid rgba(52, 211, 153, 0.4)' : '1px solid rgba(251, 191, 36, 0.5)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.82rem',
            fontWeight: 600,
          }}
        >
          <Activity size={15} color={isCertifiedScope ? '#34d399' : '#fbbf24'} />
          <span>
            {isCertifiedScope
              ? 'WITHIN FROZEN BENCHMARK LEAD SCOPE (≤ 240h): Evaluated against certified Day 22 / Day 24 benchmark lead horizons.'
              : 'EXTENDED OPERATIONAL HORIZON (264–384h): Evaluated for operational situational awareness; beyond the frozen 240h benchmark scope.'}
          </span>
        </div>
      </div>

      {/* Control Bar: Location, Variable, Lead Horizon */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '10px',
          padding: '18px 20px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' }}>
          {/* Target Location Input */}
          <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="disagreement-location-input" style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155' }}>
              TARGET LOCATION / STATION
            </label>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input
                id="disagreement-location-input"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Kolkata, Delhi, Mumbai"
                style={{
                  flex: 1,
                  padding: '9px 12px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.88rem',
                  color: '#0f172a',
                  background: '#f8fafc',
                }}
              />
            </div>
          </div>

          {/* Variable Selector */}
          <div style={{ flex: '1 1 220px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="disagreement-variable-select" style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155' }}>
              ATMOSPHERIC VARIABLE
            </label>
            <select
              id="disagreement-variable-select"
              value={variable}
              onChange={(e) => {
                setVariable(e.target.value);
                handleFetchDisagreement(location, e.target.value, leadHours);
              }}
              style={{
                padding: '9px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
                color: '#0f172a',
                background: '#ffffff',
                cursor: 'pointer',
              }}
            >
              {VARIABLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Horizon Selector */}
          <div style={{ flex: '1 1 240px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label htmlFor="disagreement-horizon-select" style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155' }}>
              LEAD HORIZON
            </label>
            <select
              id="disagreement-horizon-select"
              value={leadHours}
              onChange={(e) => {
                const lh = Number(e.target.value);
                setLeadHours(lh);
                handleFetchDisagreement(location, variable, lh);
              }}
              style={{
                padding: '9px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
                color: '#0f172a',
                background: '#ffffff',
                cursor: 'pointer',
              }}
            >
              {HORIZON_OPTIONS.map((opt) => (
                <option key={opt.lead} value={opt.lead}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Evaluate Button */}
          <button
            type="button"
            onClick={() => handleFetchDisagreement()}
            disabled={loading}
            style={{
              padding: '10px 22px',
              borderRadius: '6px',
              background: loading ? '#94a3b8' : '#0284c7',
              color: '#ffffff',
              border: 'none',
              fontWeight: 700,
              fontSize: '0.88rem',
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'background 0.2s',
            }}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            {loading ? 'Evaluating...' : 'Audit Disagreement'}
          </button>
        </div>

        {/* Preset Stations Quick Select */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', paddingTop: '4px' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
            Benchmark Presets:
          </span>
          {PRESET_STATIONS.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => {
                setLocation(preset);
                handleFetchDisagreement(preset, variable, leadHours);
              }}
              style={{
                background: location === preset ? '#e0f2fe' : '#f1f5f9',
                border: location === preset ? '1px solid #38bdf8' : '1px solid #e2e8f0',
                color: location === preset ? '#0369a1' : '#475569',
                padding: '4px 10px',
                borderRadius: '16px',
                fontSize: '0.78rem',
                fontWeight: location === preset ? 700 : 500,
                cursor: 'pointer',
              }}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      {/* Error Notice */}
      {error && (
        <div
          role="alert"
          style={{
            background: '#fee2e2',
            border: '1px solid #f87171',
            borderRadius: '8px',
            padding: '14px 18px',
            color: '#991b1b',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '0.88rem',
          }}
        >
          <AlertOctagon size={18} />
          <div>
            <strong>Evaluation Notice:</strong> {error}
          </div>
        </div>
      )}

      {/* Abstention Banner */}
      {disagreementData && disagreementData.abstain && (
        <div
          role="alert"
          style={{
            background: '#fffbeb',
            border: '1px solid #f59e0b',
            borderRadius: '8px',
            padding: '16px 20px',
            color: '#92400e',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 800, fontSize: '0.95rem' }}>
            <AlertOctagon size={18} color="#d97706" />
            OPERATIONAL ABSTENTION ENFORCED
          </div>
          <div style={{ fontSize: '0.85rem', lineHeight: 1.4 }}>
            Forecast bust inference and disagreement diagnostics are abstained for location &quot;{disagreementData.location}&quot;.
            Safety guardrails prevented model evaluation.
          </div>
          {disagreementData.reason_codes && disagreementData.reason_codes.length > 0 && (
            <div style={{ fontSize: '0.8rem', color: '#b45309', marginTop: '4px' }}>
              <strong>Reason Codes:</strong> {disagreementData.reason_codes.join(', ')}
            </div>
          )}
        </div>
      )}

      {/* Primary Analytics Grid: Strict Separation of P(BUST) and Disagreement */}
      {disagreementData && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Card 1: Calibrated P(BUST) Evidence */}
          <div
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              padding: '22px 24px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '16px',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  CALIBRATED FAILURE RISK
                </span>
                <span
                  style={{
                    background: riskColors.bg,
                    color: riskColors.text,
                    border: `1px solid ${riskColors.border}`,
                    padding: '3px 10px',
                    borderRadius: '12px',
                    fontSize: '0.78rem',
                    fontWeight: 800,
                  }}
                >
                  {disagreementData.risk_level || 'ABSTAINED'} RISK
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontSize: '2.4rem', fontWeight: 900, color: '#0f172a', letterSpacing: '-0.02em' }}>
                  {disagreementData.bust_probability !== null
                    ? `${(disagreementData.bust_probability * 100).toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#475569' }}>
                  P(BUST)
                </span>
              </div>

              <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '8px 0 0 0', lineHeight: 1.45 }}>
                Calibrated posterior probability that forecast error meets or exceeds (≥) the 95th percentile historical error threshold.
              </p>
            </div>

            <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '12px 14px', border: '1px solid #e2e8f0', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Serving Calibrator:</span>
                <span style={{ fontWeight: 700, color: '#0f172a' }}>{disagreementData.calibration_status || 'ISOTONIC'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Trust State:</span>
                <span style={{ fontWeight: 700, color: '#0f172a' }}>{disagreementData.trust_state || 'UNAVAILABLE'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Model Pipeline:</span>
                <span style={{ fontWeight: 700, color: '#0f172a' }}>V3 LightGBM (50 features)</span>
              </div>
            </div>
          </div>

          {/* Card 2: Ensemble Disagreement Summary */}
          <div
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              padding: '22px 24px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '16px',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  OBSERVED ENSEMBLE SPREAD
                </span>
                <span
                  style={{
                    background: '#e0f2fe',
                    color: '#0369a1',
                    border: '1px solid #7dd3fc',
                    padding: '3px 10px',
                    borderRadius: '12px',
                    fontSize: '0.78rem',
                    fontWeight: 700,
                  }}
                >
                  {disagreementData.member_count !== null ? `${disagreementData.member_count} Members` : 'N/A'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontSize: '2.4rem', fontWeight: 900, color: '#0284c7', letterSpacing: '-0.02em' }}>
                  {disagreementData.diagnostics?.ensemble_spread !== null && disagreementData.diagnostics?.ensemble_spread !== undefined
                    ? disagreementData.diagnostics.ensemble_spread.toFixed(2)
                    : 'N/A'}
                </span>
                <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0369a1' }}>
                  {disagreementData.units?.spread || ''}
                </span>
              </div>

              <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '8px 0 0 0', lineHeight: 1.45 }}>
                Standard deviation (&sigma;) across numerical ensemble trajectories for valid forecast time.
                Diagnostic of internal physical trajectory divergence.
              </p>
            </div>

            <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '12px 14px', border: '1px solid #e2e8f0', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Diagnostic Status:</span>
                <span style={{ fontWeight: 700, color: disagreementData.status === 'AVAILABLE' ? '#16a34a' : '#ea580c' }}>
                  {disagreementData.status}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Resolved Location:</span>
                <span style={{ fontWeight: 700, color: '#0f172a' }}>
                  {disagreementData.location}
                  {disagreementData.latitude !== null && disagreementData.longitude !== null
                    ? ` (${disagreementData.latitude.toFixed(2)}°, ${disagreementData.longitude.toFixed(2)}°)`
                    : ''}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Request ID:</span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.74rem', color: '#475569' }}>
                  {disagreementData.request_id || 'N/A'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detailed Diagnostic Metrics Breakdown */}
      {disagreementData && disagreementData.diagnostics && (
        <div
          style={{
            background: '#ffffff',
            borderRadius: '12px',
            padding: '22px 24px',
            border: '1px solid #e2e8f0',
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#0f172a' }}>
                ENSEMBLE DISPERSION METRICS DETAIL
              </h2>
              <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                All metrics derived from live NOAA GEFS perturbation members without synthetic thresholds.
              </span>
            </div>
            <span style={{ fontSize: '0.76rem', background: '#f1f5f9', color: '#475569', padding: '4px 10px', borderRadius: '6px', fontWeight: 600 }}>
              Lead Horizon: {disagreementData.lead_hours}h
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
            {/* Metric: Ensemble Standard Deviation (Spread) */}
            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                Ensemble Spread (&sigma;)
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
                {disagreementData.diagnostics.ensemble_spread !== null && disagreementData.diagnostics.ensemble_spread !== undefined
                  ? `${disagreementData.diagnostics.ensemble_spread.toFixed(2)} ${disagreementData.units?.spread || ''}`
                  : 'N/A'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748b' }}>Standard deviation across 31 members</div>
            </div>

            {/* Metric: Ensemble Range */}
            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                Ensemble Range (Max - Min)
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
                {disagreementData.diagnostics.ensemble_range !== null && disagreementData.diagnostics.ensemble_range !== undefined
                  ? `${disagreementData.diagnostics.ensemble_range.toFixed(2)} ${disagreementData.units?.range || ''}`
                  : 'N/A'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748b' }}>Full member envelope difference</div>
            </div>

            {/* Metric: Interquartile Range (IQR) */}
            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                IQR (Q75 - Q25)
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
                {disagreementData.diagnostics.ensemble_iqr !== null && disagreementData.diagnostics.ensemble_iqr !== undefined
                  ? `${disagreementData.diagnostics.ensemble_iqr.toFixed(2)} ${disagreementData.units?.iqr || ''}`
                  : 'N/A'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748b' }}>Robust 50% core member spread</div>
            </div>

            {/* Metric: Coefficient of Variation (CV) */}
            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                Coeff. of Variation (CV)
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
                {disagreementData.diagnostics.ensemble_cv !== null && disagreementData.diagnostics.ensemble_cv !== undefined
                  ? disagreementData.diagnostics.ensemble_cv.toFixed(4)
                  : 'N/A'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748b' }}>&sigma; / |&mu;| (Dimensionless ratio)</div>
            </div>

            {/* Metric: Spread to IQR Ratio */}
            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                Spread to IQR Ratio
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
                {disagreementData.diagnostics.spread_to_iqr_ratio !== null && disagreementData.diagnostics.spread_to_iqr_ratio !== undefined
                  ? disagreementData.diagnostics.spread_to_iqr_ratio.toFixed(2)
                  : 'N/A'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748b' }}>Tail-heaviness indicator (&sigma;/IQR)</div>
            </div>

            {/* Metric: Ensemble Trajectory Extremes */}
            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                Ensemble Mean [&mu;] (Min, Max)
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', margin: '6px 0' }}>
                {disagreementData.diagnostics.ensemble_mean !== null && disagreementData.diagnostics.ensemble_mean !== undefined
                  ? `${disagreementData.diagnostics.ensemble_mean.toFixed(1)} ${disagreementData.units?.mean || ''}`
                  : 'N/A'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748b' }}>
                {disagreementData.diagnostics.ensemble_min !== null && disagreementData.diagnostics.ensemble_max !== null
                  ? `Min: ${disagreementData.diagnostics.ensemble_min?.toFixed(1)} | Max: ${disagreementData.diagnostics.ensemble_max?.toFixed(1)}`
                  : 'Extrema unavailable'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Educational Operational Panel: Disagreement != P(BUST) */}
      <div
        style={{
          background: '#f8fafc',
          borderRadius: '10px',
          padding: '18px 22px',
          border: '1px solid #cbd5e1',
          display: 'flex',
          gap: '14px',
          alignItems: 'flex-start',
        }}
      >
        <HelpCircle size={24} color="#0284c7" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '0.85rem', color: '#334155', lineHeight: 1.5 }}>
          <div style={{ fontWeight: 800, color: '#0f172a', marginBottom: '4px', fontSize: '0.9rem' }}>
            OPERATIONAL NOTE: FORECAST DISAGREEMENT ≠ P(BUST)
          </div>
          <div>
            <strong>Ensemble disagreement</strong> describes the statistical dispersion among the 31 numerical ensemble trajectories produced by the operational GEFS model.
            It is a diagnostic measure of atmospheric chaos and solution sensitivity for the selected lead time.
          </div>
          <div style={{ marginTop: '4px' }}>
            <strong>Calibrated P(BUST)</strong> is the machine-learned probability, verified under Day 22 isotonic calibration, that the forecast absolute error will meet or exceed the operational failure threshold.
            High disagreement does not guarantee a bust; low disagreement does not guarantee forecast accuracy.
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForecastDisagreementPanel;
