import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Activity,
  AlertOctagon,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Layers,
  ShieldCheck,
  Clock,
  MapPin,
  GitCompare,
} from 'lucide-react';
import { apiClient } from '../api/client';
import {
  ForecastRevisionResponse,
  RiskLevel,
} from '../api/types';

interface ForecastRevisionPanelProps {
  initialLocation?: string;
  initialVariable?: string;
  initialLeadHours?: number;
  onNavigateToDisagreement?: () => void;
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

export const ForecastRevisionPanel: React.FC<ForecastRevisionPanelProps> = ({
  initialLocation = 'Kolkata',
  initialVariable = 'temperature_2m',
  initialLeadHours = 24,
  onNavigateToDisagreement,
  onNavigateToMultiLocation,
}) => {
  const [location, setLocation] = useState<string>(initialLocation);
  const [variable, setVariable] = useState<string>(initialVariable);
  const [leadHours, setLeadHours] = useState<number>(initialLeadHours);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [revisionData, setRevisionData] = useState<ForecastRevisionResponse | null>(null);

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

  const handleFetchRevision = async (locToUse = location, varToUse = variable, leadToUse = leadHours) => {
    if (!locToUse.trim()) {
      setError('Please provide a target location.');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const { data, error: apiError } = await apiClient.getForecastRevision({
        location: locToUse.trim(),
        variable: varToUse,
        lead_hours: leadToUse,
      });

      if (apiError) {
        setError(apiError.message || apiError.error || 'Revision intelligence evaluation failed.');
        setRevisionData(null);
      } else if (data) {
        setRevisionData(data);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unexpected failure communicating with Veyra.');
      setRevisionData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleFetchRevision(location, variable, leadHours);
  }, []);

  const getRiskBadgeColor = (risk?: RiskLevel | null) => {
    switch (risk) {
      case 'CRITICAL':
        return '#dc2626';
      case 'HIGH':
        return '#ea580c';
      case 'MEDIUM':
        return '#d97706';
      case 'LOW':
        return '#16a34a';
      default:
        return '#6b7280';
    }
  };

  const getDirectionBadge = (dir?: string) => {
    switch (dir) {
      case 'INCREASED':
        return {
          icon: <ArrowUpRight size={16} />,
          color: '#3b82f6',
          bg: '#eff6ff',
          label: 'INCREASED',
        };
      case 'DECREASED':
        return {
          icon: <ArrowDownRight size={16} />,
          color: '#0284c7',
          bg: '#f0f9ff',
          label: 'DECREASED',
        };
      case 'UNCHANGED':
        return {
          icon: <Minus size={16} />,
          color: '#64748b',
          bg: '#f8fafc',
          label: 'UNCHANGED',
        };
      default:
        return null;
    }
  };

  const unitLabel = revisionData?.units?.value || VARIABLE_OPTIONS.find((v) => v.value === variable)?.unit || '';

  return (
    <div className="forecast-disagreement-panel" style={{ padding: '24px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Header Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          background: 'linear-gradient(135deg, #0b2545 0%, #134074 100%)',
          color: '#ffffff',
          padding: '24px',
          borderRadius: '12px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
          marginBottom: '24px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <TrendingUp size={28} style={{ color: '#38bdf8' }} />
            <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
              FORECAST REVISION / TRAJECTORY INTELLIGENCE
            </h1>
            <span
              style={{
                background: '#0284c7',
                color: '#ffffff',
                fontSize: '0.72rem',
                fontWeight: 800,
                padding: '3px 8px',
                borderRadius: '6px',
                letterSpacing: '0.04em',
              }}
            >
              DAY 30
            </span>
          </div>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.88rem', maxWidth: '850px' }}>
            Revision diagnostics are shown only when durable, provider-verified issue-cycle evidence exists for the exact
            same target. Strictly distinguishes <strong>Forecast Revision ≠ Ensemble Disagreement ≠ Calibrated P(BUST)</strong>.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => handleFetchRevision()}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: '#0284c7',
              color: '#ffffff',
              border: 'none',
              padding: '10px 16px',
              borderRadius: '8px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            {loading ? 'Evaluating...' : 'Re-Evaluate'}
          </button>
        </div>
      </div>

      {/* Target Selection Controls */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '12px',
          border: '1px solid #e2e8f0',
          padding: '20px',
          marginBottom: '24px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'flex-end' }}>
          {/* Location Input & Presets */}
          <div style={{ flex: '1 1 260px' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
              TARGET LOCATION / COORDINATES
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Kolkata or 22.57,88.36"
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
                marginBottom: '8px',
                boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {PRESET_STATIONS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => {
                    setLocation(preset);
                    handleFetchRevision(preset, variable, leadHours);
                  }}
                  style={{
                    background: location.toLowerCase() === preset.toLowerCase() ? '#0284c7' : '#f1f5f9',
                    color: location.toLowerCase() === preset.toLowerCase() ? '#ffffff' : '#334155',
                    border: '1px solid #cbd5e1',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          {/* Meteorological Variable */}
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
              METEOROLOGICAL VARIABLE
            </label>
            <select
              value={variable}
              onChange={(e) => {
                const newVar = e.target.value;
                setVariable(newVar);
                handleFetchRevision(location, newVar, leadHours);
              }}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
                background: '#ffffff',
                boxSizing: 'border-box',
              }}
            >
              {VARIABLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Lead Horizon */}
          <div style={{ flex: '1 1 240px' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
              FORECAST HORIZON (LEAD HOURS)
            </label>
            <select
              value={leadHours}
              onChange={(e) => {
                const newLead = parseInt(e.target.value, 10);
                setLeadHours(newLead);
                handleFetchRevision(location, variable, newLead);
              }}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
                background: '#ffffff',
                boxSizing: 'border-box',
              }}
            >
              {HORIZON_OPTIONS.map((opt) => (
                <option key={opt.lead} value={opt.lead}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Horizon Certification Badge */}
          <div style={{ paddingBottom: '4px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 700,
                background: isCertifiedScope ? '#ecfdf5' : '#fffbeb',
                color: isCertifiedScope ? '#065f46' : '#92400e',
                border: `1px solid ${isCertifiedScope ? '#a7f3d0' : '#fde68a'}`,
              }}
            >
              <ShieldCheck size={16} />
              {isCertifiedScope
                ? 'Within Frozen Benchmark Lead Scope (<= 240h)'
                : 'Extended Operational Horizon (264h–384h)'}
            </span>
          </div>
        </div>
      </div>

      {/* Error View */}
      {error && (
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#b91c1c',
            padding: '16px',
            borderRadius: '8px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertOctagon size={20} />
          <div>
            <strong>Evaluation Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Abstention State */}
      {revisionData?.abstain && (
        <div
          style={{
            background: '#fff1f2',
            border: '1px solid #fecdd3',
            color: '#9f1239',
            padding: '24px',
            borderRadius: '12px',
            marginBottom: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <AlertOctagon size={24} style={{ color: '#e11d48' }} />
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>
              SAFETY ABSTENTION ACTIVE — NO FORECAST REVISION COMPUTED
            </h3>
          </div>
          <p style={{ margin: '0 0 12px 0', fontSize: '0.9rem', color: '#881337' }}>
            The target location <strong>&quot;{location}&quot;</strong> could not be geocoded or validated safely. Veyra strictly abstains from manufacturing synthetic trajectory data or computing fake zero revision deltas on unvalidated locations.
          </p>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {revisionData.reason_codes.map((rc) => (
              <span
                key={rc}
                style={{
                  background: '#ffe4e6',
                  color: '#9f1239',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  fontFamily: 'monospace',
                }}
              >
                {rc}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Prior Run Unavailable State */}
      {revisionData && !revisionData.abstain && revisionData.status === 'INSUFFICIENT_HISTORY' && (
        <div
          style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            padding: '24px',
            borderRadius: '12px',
            marginBottom: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <Clock size={24} style={{ color: '#0284c7' }} />
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#0f172a' }}>
              INSUFFICIENT COMPARABLE ISSUE-CYCLE HISTORY
            </h3>
          </div>
          <p style={{ margin: '0 0 16px 0', fontSize: '0.9rem', color: '#475569', lineHeight: 1.5 }}>
            Veyra does not currently have durable, provider-verified forecast runs needed to compare this exact target
            (<strong>{revisionData.resolved_name || revisionData.location}</strong> • <strong>{revisionData.variable}</strong> • valid at <strong>{revisionData.valid_time}</strong>).
            No previous run, revision delta, or trajectory is manufactured. <strong>Missing revision evidence remains null and is never converted to fake 0.0.</strong>
          </p>
        </div>
      )}

      {/* Main Results Display */}
      {revisionData && !revisionData.abstain && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px', marginBottom: '24px' }}>
          {/* Card 1: Run-to-Run Revision Diagnostics */}
          <div
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              border: '1px solid #e2e8f0',
              padding: '24px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <TrendingUp size={20} style={{ color: '#0284c7' }} />
                <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>
                  RUN-TO-RUN REVISION
                </h2>
              </div>
              {revisionData.trajectory?.direction && (
                (() => {
                  const badge = getDirectionBadge(revisionData.trajectory.direction);
                  return badge ? (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '4px 10px',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        fontWeight: 800,
                        background: badge.bg,
                        color: badge.color,
                        border: `1px solid ${badge.color}33`,
                      }}
                    >
                      {badge.icon}
                      {badge.label}
                    </span>
                  ) : null;
                })()
              )}
            </div>

            {revisionData.trajectory ? (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                  <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                      PREVIOUS RUN
                    </div>
                    <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#334155', marginTop: '4px' }}>
                      {revisionData.trajectory.previous_value} {unitLabel}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '4px' }}>
                      {revisionData.previous_issue_time || 'Prior Cycle'}
                    </div>
                  </div>

                  <div style={{ background: '#f0f9ff', padding: '14px', borderRadius: '8px', border: '1px solid #bae6fd' }}>
                    <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#0369a1', textTransform: 'uppercase' }}>
                      CURRENT RUN
                    </div>
                    <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#0369a1', marginTop: '4px' }}>
                      {revisionData.trajectory.current_value} {unitLabel}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#0284c7', marginTop: '4px' }}>
                      {revisionData.current_issue_time}
                    </div>
                  </div>
                </div>

                <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.85rem', color: '#475569' }}>Signed Revision Delta:</span>
                    <strong style={{ fontSize: '1.1rem', color: revisionData.trajectory.revision_delta > 0 ? '#2563eb' : revisionData.trajectory.revision_delta < 0 ? '#0284c7' : '#475569' }}>
                      {revisionData.trajectory.revision_delta > 0 ? `+${revisionData.trajectory.revision_delta}` : revisionData.trajectory.revision_delta} {unitLabel}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.85rem', color: '#475569' }}>Absolute Revision Magnitude:</span>
                    <strong style={{ fontSize: '1.05rem', color: '#0f172a' }}>
                      {revisionData.trajectory.absolute_revision} {unitLabel}
                    </strong>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8', fontStyle: 'italic', marginTop: '8px' }}>
                    * Direction is a deterministic mathematical label (INCREASED/DECREASED/UNCHANGED) indicating sign of change, not forecast quality or correctness.
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ color: '#64748b', fontSize: '0.88rem', padding: '16px 0' }}>
                Run-to-run revision delta is unavailable because a comparable prior forecast cycle has not yet been recorded for this valid target time.
              </div>
            )}
          </div>

          {/* Card 2: Ensemble Distribution Revision */}
          <div
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              border: '1px solid #e2e8f0',
              padding: '24px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Layers size={20} style={{ color: '#6366f1' }} />
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>
                ENSEMBLE DISTRIBUTION EVOLUTION
              </h2>
            </div>

            {revisionData.ensemble_revision && revisionData.ensemble_revision.current_mean !== null ? (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                  <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b' }}>ENSEMBLE MEAN</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#334155', marginTop: '2px' }}>
                      {revisionData.ensemble_revision.current_mean} {unitLabel}
                    </div>
                    {revisionData.ensemble_revision.mean_delta !== null && (
                      <div style={{ fontSize: '0.75rem', color: '#6366f1', marginTop: '4px' }}>
                        Δ: {revisionData.ensemble_revision.mean_delta > 0 ? `+${revisionData.ensemble_revision.mean_delta}` : revisionData.ensemble_revision.mean_delta} {unitLabel}
                      </div>
                    )}
                  </div>

                  <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b' }}>ENSEMBLE SPREAD (STD)</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#334155', marginTop: '2px' }}>
                      {revisionData.ensemble_revision.current_spread} {unitLabel}
                    </div>
                    {revisionData.ensemble_revision.spread_delta !== null && (
                      <div style={{ fontSize: '0.75rem', color: '#6366f1', marginTop: '4px' }}>
                        Δ: {revisionData.ensemble_revision.spread_delta > 0 ? `+${revisionData.ensemble_revision.spread_delta}` : revisionData.ensemble_revision.spread_delta} {unitLabel}
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ fontSize: '0.75rem', color: '#64748b', lineHeight: 1.4 }}>
                  Shows shift in the underlying NOAA GEFS 31-member distribution mean and spread between consecutive issue cycles for the same target time.
                </div>
              </div>
            ) : (
              <div style={{ color: '#64748b', fontSize: '0.88rem', padding: '16px 0' }}>
                Ensemble distribution comparison unavailable until consecutive runs are recorded.
              </div>
            )}
          </div>

          {/* Card 3: Calibrated Operational Bust Risk (P(BUST)) */}
          <div
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              border: '1px solid #e2e8f0',
              padding: '24px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={20} style={{ color: '#0ea5e9' }} />
                <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>
                  CALIBRATED FAILURE RISK
                </h2>
              </div>
              {revisionData.risk_level && (
                <span
                  style={{
                    backgroundColor: getRiskBadgeColor(revisionData.risk_level),
                    color: '#ffffff',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                  }}
                >
                  {revisionData.risk_level}
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '12px' }}>
              <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#0f172a' }}>
                {revisionData.bust_probability !== null
                  ? `${(revisionData.bust_probability * 100).toFixed(1)}%`
                  : 'N/A'}
              </span>
              <span style={{ color: '#64748b', fontSize: '0.85rem' }}>P(BUST)</span>
            </div>

            <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '10px', fontSize: '0.75rem', color: '#64748b' }}>
              <div>Trust State: <strong>{revisionData.trust_state}</strong></div>
              <div>Calibration: <strong>{revisionData.calibration_status || 'ISOTONIC'}</strong></div>
              <div style={{ marginTop: '6px', color: '#0284c7', fontWeight: 600 }}>
                Strict separation: Revision Delta ≠ Ensemble Spread ≠ P(BUST)
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Discrete Trajectory Visualization (Only when >= 2 points) */}
      {revisionData?.trajectory_points && revisionData.trajectory_points.length >= 2 && (
        <div
          style={{
            background: '#ffffff',
            borderRadius: '12px',
            border: '1px solid #e2e8f0',
            padding: '24px',
            marginBottom: '24px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <TrendingUp size={20} style={{ color: '#0284c7' }} />
            <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>
              REAL ISSUE-CYCLE TRAJECTORY EVOLUTION
            </h2>
          </div>
          <p style={{ margin: '0 0 20px 0', fontSize: '0.85rem', color: '#64748b' }}>
            Discrete verified issue cycles for valid time <strong>{revisionData.valid_time}</strong>. No synthetic intermediate points or smoothed fake curves are generated.
          </p>

          <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'center' }}>
            {revisionData.trajectory_points.map((point, idx) => (
              <div
                key={point.issue_time}
                style={{
                  flex: '1 1 200px',
                  background: idx === revisionData.trajectory_points.length - 1 ? '#f0f9ff' : '#f8fafc',
                  border: `1px solid ${idx === revisionData.trajectory_points.length - 1 ? '#bae6fd' : '#e2e8f0'}`,
                  borderRadius: '8px',
                  padding: '16px',
                }}
              >
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b' }}>
                  {idx === 0 ? 'CYCLE 1 (PRIOR RUN)' : 'CYCLE 2 (CURRENT RUN)'}
                </div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
                  {point.forecast_value} {unitLabel}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#475569' }}>
                  Lead: {point.lead_hours}h
                </div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '4px' }}>
                  Issue: {point.issue_time}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Target Provenance and Metadata */}
      {revisionData && (
        <div
          style={{
            background: '#f8fafc',
            borderRadius: '8px',
            padding: '16px',
            border: '1px solid #e2e8f0',
            fontSize: '0.8rem',
            color: '#64748b',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div>
            <strong>Standardized Target:</strong> {revisionData.resolved_name || revisionData.location}{' '}
            {revisionData.latitude != null && revisionData.longitude != null && (
              <span>({revisionData.latitude.toFixed(2)}°N, {revisionData.longitude.toFixed(2)}°E)</span>
            )}
          </div>
          <div>
            <strong>Valid Target Time:</strong> {revisionData.valid_time || 'N/A'}
          </div>
          <div>
            <strong>Scientific Horizon:</strong> {revisionData.scientific_scope}
          </div>
          <div>
            <strong>Request ID:</strong> <code style={{ color: '#0284c7' }}>{revisionData.request_id}</code>
          </div>
        </div>
      )}

      {/* Cross-Feature Navigation */}
      <div style={{ display: 'flex', gap: '12px', marginTop: '24px', flexWrap: 'wrap' }}>
        {onNavigateToDisagreement && (
          <button
            type="button"
            onClick={onNavigateToDisagreement}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: '#f1f5f9',
              border: '1px solid #cbd5e1',
              padding: '8px 14px',
              borderRadius: '6px',
              fontSize: '0.82rem',
              fontWeight: 600,
              color: '#334155',
              cursor: 'pointer',
            }}
          >
            <GitCompare size={14} /> View Day 29 Forecast Disagreement
          </button>
        )}

        {onNavigateToMultiLocation && (
          <button
            type="button"
            onClick={onNavigateToMultiLocation}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: '#f1f5f9',
              border: '1px solid #cbd5e1',
              padding: '8px 14px',
              borderRadius: '6px',
              fontSize: '0.82rem',
              fontWeight: 600,
              color: '#334155',
              cursor: 'pointer',
            }}
          >
            <MapPin size={14} /> View Day 28 Multi-Location Matrix
          </button>
        )}
      </div>
    </div>
  );
};

export default ForecastRevisionPanel;
