import React, { useState, useEffect, useMemo } from 'react';
import {
  Layers,
  ArrowUpDown,
  RefreshCw,
  Info,
  AlertOctagon,
  Search,
  ExternalLink,
  ChevronRight,
  Table as TableIcon,
  LayoutGrid,
  GitCompare,
} from 'lucide-react';
import { apiClient } from '../api/client';
import {
  RiskLevel,
  SpatialReliabilityPoint,
  SpatialReliabilityResponse,
} from '../api/types';
import { INDIAN_BENCHMARK_25_STATIONS } from '../data/locations';

const MAJOR_METROS = ['Delhi', 'Kolkata', 'Mumbai', 'Chennai', 'Bengaluru'];
const NORTH_SOUTH = ['Delhi', 'Srinagar', 'Leh', 'Chennai', 'Thiruvananthapuram', 'Kochi'];

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
  { lead: 240, label: '240h (10 Days) [Benchmark Scope Limit]', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 264, label: '264h (11 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 288, label: '288h (12 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 312, label: '312h (13 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 336, label: '336h (14 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 360, label: '360h (15 Days) [Extended Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 384, label: '384h (16 Days) [Max Operational Horizon]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
];

export type SortField = 'prob_desc' | 'prob_asc' | 'risk_desc' | 'name_asc' | 'input_order';
export type FilterRisk = 'ALL' | 'ELEVATED' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'ABSTAINED';

interface MultiLocationPanelProps {
  onNavigateToSpatial?: (locationName?: string) => void;
  onNavigateToDisagreement?: (locationName?: string, variable?: string, leadHours?: number) => void;
}

export const MultiLocationPanel: React.FC<MultiLocationPanelProps> = ({ onNavigateToSpatial, onNavigateToDisagreement }) => {
  const [stationPreset, setStationPreset] = useState<'25_STATIONS' | 'METROS' | 'NORTH_SOUTH' | 'CUSTOM'>('25_STATIONS');
  const [customLocationsText, setCustomLocationsText] = useState<string>('Delhi, Kolkata, Mumbai, Chennai, Bengaluru');
  const [variable, setVariable] = useState<string>('temperature_2m');
  const [leadHours, setLeadHours] = useState<number>(24);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [spatialData, setSpatialData] = useState<SpatialReliabilityResponse | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<SpatialReliabilityPoint | null>(null);

  // View preferences
  const [displayMode, setDisplayMode] = useState<'cards' | 'table'>('cards');
  const [sortField, setSortField] = useState<SortField>('prob_desc');
  const [filterRisk, setFilterRisk] = useState<FilterRisk>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const isCertifiedScope = leadHours <= 240;

  // Active location list
  const activeLocations = useMemo(() => {
    if (stationPreset === '25_STATIONS') return INDIAN_BENCHMARK_25_STATIONS;
    if (stationPreset === 'METROS') return MAJOR_METROS;
    if (stationPreset === 'NORTH_SOUTH') return NORTH_SOUTH;
    return customLocationsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }, [stationPreset, customLocationsText]);

  // Execute multi-location evaluation via authoritative endpoint
  const handleEvaluate = async () => {
    if (activeLocations.length === 0) {
      setError('Please provide at least one location to evaluate.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { data, error: apiError } = await apiClient.getSpatialReliability({
        locations: activeLocations,
        variable,
        lead_hours: leadHours,
      });

      if (apiError) {
        setError(apiError.message || 'Multi-location evaluation request failed.');
        setSpatialData(null);
        setSelectedPoint(null);
      } else if (data) {
        setSpatialData(data);
        const firstAvailable = data.points.find((p) => !p.abstain && p.bust_probability != null);
        setSelectedPoint(firstAvailable || data.points[0] || null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unexpected communication failure.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleEvaluate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getRiskColor = (risk: RiskLevel | null, abstain: boolean) => {
    if (abstain || risk === null) return '#64748b'; // neutral slate
    switch (risk) {
      case 'LOW':
        return '#10b981';
      case 'MEDIUM':
        return '#f59e0b';
      case 'HIGH':
        return '#ef4444';
      case 'CRITICAL':
        return '#8b5cf6';
      default:
        return '#64748b';
    }
  };

  const getRiskBadge = (risk: RiskLevel | null, abstain: boolean) => {
    if (abstain || risk === null) {
      return (
        <span
          style={{
            background: '#e2e8f0',
            color: '#475569',
            padding: '3px 8px',
            borderRadius: '6px',
            fontSize: '0.72rem',
            fontWeight: 800,
            letterSpacing: '0.04em',
          }}
        >
          ABSTAINED
        </span>
      );
    }
    const color = getRiskColor(risk, false);
    return (
      <span
        style={{
          background: `${color}18`,
          color: color,
          border: `1px solid ${color}40`,
          padding: '3px 8px',
          borderRadius: '6px',
          fontSize: '0.72rem',
          fontWeight: 800,
          letterSpacing: '0.04em',
        }}
      >
        {risk} RISK
      </span>
    );
  };

  // Filter & sort points
  const processedPoints = useMemo(() => {
    if (!spatialData?.points) return [];
    let list = [...spatialData.points];

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(
        (p) =>
          p.location.toLowerCase().includes(q) ||
          (p.resolved_name && p.resolved_name.toLowerCase().includes(q)) ||
          (p.region_id && p.region_id.toLowerCase().includes(q))
      );
    }

    // Filter by risk tier
    if (filterRisk === 'ELEVATED') {
      list = list.filter(
        (p) => !p.abstain && (p.risk_level === 'MEDIUM' || p.risk_level === 'HIGH' || p.risk_level === 'CRITICAL')
      );
    } else if (filterRisk === 'LOW') {
      list = list.filter((p) => !p.abstain && p.risk_level === 'LOW');
    } else if (filterRisk === 'MEDIUM') {
      list = list.filter((p) => !p.abstain && p.risk_level === 'MEDIUM');
    } else if (filterRisk === 'HIGH') {
      list = list.filter((p) => !p.abstain && p.risk_level === 'HIGH');
    } else if (filterRisk === 'CRITICAL') {
      list = list.filter((p) => !p.abstain && p.risk_level === 'CRITICAL');
    } else if (filterRisk === 'ABSTAINED') {
      list = list.filter((p) => p.abstain || p.risk_level === null);
    }

    // Sort
    list.sort((a, b) => {
      if (sortField === 'prob_desc') {
        const pA = a.bust_probability ?? -1;
        const pB = b.bust_probability ?? -1;
        return pB - pA;
      }
      if (sortField === 'prob_asc') {
        const pA = a.bust_probability ?? 999;
        const pB = b.bust_probability ?? 999;
        return pA - pB;
      }
      if (sortField === 'risk_desc') {
        const riskWeight: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
        const wA = a.risk_level ? riskWeight[a.risk_level] || 0 : -1;
        const wB = b.risk_level ? riskWeight[b.risk_level] || 0 : -1;
        return wB - wA;
      }
      if (sortField === 'name_asc') {
        const nameA = a.resolved_name || a.location;
        const nameB = b.resolved_name || b.location;
        return nameA.localeCompare(nameB);
      }
      return 0; // input_order
    });

    return list;
  }, [spatialData, searchQuery, filterRisk, sortField]);

  const availableCount = spatialData?.summary?.available_locations ?? 0;
  const abstainedCount = spatialData?.summary?.abstained_locations ?? 0;
  const elevatedCount = spatialData?.summary?.elevated_risk_locations ?? 0;
  const lowCount = spatialData?.summary?.low_risk_locations ?? 0;

  return (
    <div className="multi-location-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header Card */}
      <div
        className="multi-location-header-card"
        style={{
          background: 'linear-gradient(135deg, #091e3a 0%, #0f2b48 100%)',
          borderRadius: '14px',
          padding: '24px 28px',
          color: '#ffffff',
          boxShadow: '0 4px 16px rgba(0, 43, 73, 0.25)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ background: '#0284c7', padding: '6px', borderRadius: '8px', display: 'flex' }}>
                <Layers size={22} color="#ffffff" />
              </div>
              <h1 style={{ margin: 0, fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.01em' }}>
                Multi-Location Reliability Intelligence
              </h1>
              <span
                style={{
                  background: isCertifiedScope ? '#059669' : '#d97706',
                  color: '#ffffff',
                  padding: '3px 10px',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  letterSpacing: '0.04em',
                }}
              >
                {isCertifiedScope ? 'WITHIN FROZEN BENCHMARK LEAD SCOPE (<=240h)' : 'EXTENDED OPERATIONAL HORIZON (264h-384h)'}
              </span>
            </div>
            <p style={{ margin: '8px 0 0 0', color: '#94a3b8', fontSize: '0.88rem', maxWidth: '850px', lineHeight: 1.5 }}>
              Compares and inspects forecast reliability intelligence across multiple evaluated stations using Veyra&apos;s frozen
              V3 LightGBM model and isotonic calibrator. <strong>Objective reliability comparison:</strong> evaluates
              discrete point-level forecast bust risk without synthetic spatial interpolation or weather severity ranking.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {onNavigateToSpatial && (
              <button
                type="button"
                onClick={() => onNavigateToSpatial(selectedPoint?.resolved_name || selectedPoint?.location)}
                style={{
                  background: '#1e293b',
                  color: '#38bdf8',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  padding: '10px 16px',
                  fontWeight: 700,
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
              >
                <ExternalLink size={15} />
                <span>View on Spatial Map</span>
              </button>
            )}

            {onNavigateToDisagreement && (
              <button
                type="button"
                onClick={() => onNavigateToDisagreement(selectedPoint?.resolved_name || selectedPoint?.location, variable, leadHours)}
                style={{
                  background: '#1e293b',
                  color: '#a5b4fc',
                  border: '1px solid #4338ca',
                  borderRadius: '8px',
                  padding: '10px 16px',
                  fontWeight: 700,
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
              >
                <GitCompare size={15} />
                <span>Disagreement Intel</span>
              </button>
            )}

            <button
              type="button"
              onClick={handleEvaluate}
              disabled={loading}
              style={{
                background: loading ? '#475569' : '#0284c7',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                padding: '10px 18px',
                fontWeight: 700,
                fontSize: '0.88rem',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.2s ease',
              }}
            >
              <RefreshCw size={16} className={loading ? 'spin' : ''} />
              {loading ? 'Evaluating...' : 'Refresh Multi-Location Intelligence'}
            </button>
          </div>
        </div>
      </div>

      {/* Control Bar: Selection Preset, Variable, Horizon */}
      <div
        className="multi-location-controls-card"
        style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          padding: '16px 20px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          alignItems: 'end',
          boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
        }}
      >
        {/* Preset Selector */}
        <div>
          <label htmlFor="multi-station-preset-select" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
            Station Selection Preset
          </label>
          <select
            id="multi-station-preset-select"
            value={stationPreset}
            onChange={(e) => setStationPreset(e.target.value as any)}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.88rem',
              fontWeight: 600,
              color: '#1e293b',
              background: '#f8fafc',
            }}
          >
            <option value="25_STATIONS">25 Indian Meteorological Stations</option>
            <option value="METROS">Major Metros (5 Stations)</option>
            <option value="NORTH_SOUTH">North-South Transect (6 Stations)</option>
            <option value="CUSTOM">Custom Station List</option>
          </select>
        </div>

        {/* Variable Selector */}
        <div>
          <label htmlFor="multi-variable-select" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
            Meteorological Variable
          </label>
          <select
            id="multi-variable-select"
            value={variable}
            onChange={(e) => setVariable(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.88rem',
              fontWeight: 600,
              color: '#1e293b',
              background: '#f8fafc',
            }}
          >
            <option value="temperature_2m">2m Temperature (temperature_2m)</option>
            <option value="wind_speed_10m">10m Wind Speed (wind_speed_10m)</option>
            <option value="surface_pressure">Surface Pressure (surface_pressure)</option>
          </select>
        </div>

        {/* Forecast Horizon Selector */}
        <div>
          <label htmlFor="multi-horizon-select" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
            <span>Forecast Lead Horizon</span>
            <span style={{ color: isCertifiedScope ? '#059669' : '#d97706', fontWeight: 700 }}>
              {isCertifiedScope ? 'Within Benchmark Scope' : 'Extended Operational'}
            </span>
          </label>
          <select
            id="multi-horizon-select"
            value={leadHours}
            onChange={(e) => setLeadHours(Number(e.target.value))}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '6px',
              border: `1px solid ${isCertifiedScope ? '#cbd5e1' : '#f59e0b'}`,
              fontSize: '0.88rem',
              fontWeight: 600,
              color: '#1e293b',
              background: isCertifiedScope ? '#f8fafc' : '#fffbeb',
            }}
          >
            <optgroup label="Within Frozen Benchmark Lead Scope (<=240h)">
              {HORIZON_OPTIONS.filter((h) => h.scope === 'FROZEN_BENCHMARK_LEAD_SCOPE').map((h) => (
                <option key={h.lead} value={h.lead}>
                  {h.label}
                </option>
              ))}
            </optgroup>
            <optgroup label="Extended Operational Horizon (264h–384h)">
              {HORIZON_OPTIONS.filter((h) => h.scope === 'EXTENDED_OPERATIONAL_HORIZON').map((h) => (
                <option key={h.lead} value={h.lead}>
                  {h.label}
                </option>
              ))}
            </optgroup>
          </select>
        </div>
      </div>

      {/* Custom Locations Input Box if CUSTOM selected */}
      {stationPreset === 'CUSTOM' && (
        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            padding: '14px 20px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          }}
        >
          <label htmlFor="multi-custom-locations-input" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
            Custom Location Queries (Comma-separated city names or coordinates)
          </label>
          <input
            id="multi-custom-locations-input"
            type="text"
            value={customLocationsText}
            onChange={(e) => setCustomLocationsText(e.target.value)}
            placeholder="e.g. Kolkata, Delhi, Mumbai, 22.57,88.36"
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.88rem',
            }}
          />
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div
          className="abstention-box"
          role="alert"
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '10px',
            padding: '14px 18px',
            color: '#991b1b',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertOctagon size={20} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>Multi-Location Query Alert</div>
            <div style={{ fontSize: '0.82rem', marginTop: '2px' }}>{error}</div>
          </div>
        </div>
      )}

      {/* Summary KPI Grid */}
      {spatialData?.summary && (
        <div
          className="multi-summary-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
            gap: '12px',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>TOTAL EVALUATED</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
              {spatialData.summary.total_locations}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
              {availableCount} Available | {abstainedCount} Abstained
            </div>
          </div>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>HIGHEST EVALUATED P(BUST)</div>
            <div
              style={{
                fontSize: '1.5rem',
                fontWeight: 800,
                color:
                  spatialData.summary.max_bust_probability != null
                    ? getRiskColor(spatialData.summary.max_risk_level, false)
                    : '#94a3b8',
                marginTop: '4px',
              }}
            >
              {spatialData.summary.max_bust_probability != null
                ? `${(spatialData.summary.max_bust_probability * 100).toFixed(1)}%`
                : 'N/A'}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px', fontWeight: 600 }}>
              {spatialData.summary.max_risk_location || 'None'}
            </div>
          </div>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>MEAN BUST PROBABILITY</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
              {spatialData.summary.mean_bust_probability != null
                ? `${(spatialData.summary.mean_bust_probability * 100).toFixed(1)}%`
                : 'N/A'}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>Across valid stations</div>
          </div>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>ELEVATED RISK LOCATIONS</div>
            <div
              style={{
                fontSize: '1.5rem',
                fontWeight: 800,
                color: elevatedCount > 0 ? '#ea580c' : '#10b981',
                marginTop: '4px',
              }}
            >
              {elevatedCount}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>Medium, High, Critical</div>
          </div>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>SCIENTIFIC SCOPE</div>
            <div
              style={{
                fontSize: '0.88rem',
                fontWeight: 800,
                color: isCertifiedScope ? '#059669' : '#d97706',
                marginTop: '8px',
              }}
            >
              {isCertifiedScope ? 'WITHIN FROZEN BENCHMARK LEAD SCOPE' : 'EXTENDED OPERATIONAL HORIZON'}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
              {leadHours}h Lead Horizon
            </div>
          </div>
        </div>
      )}

      {/* Filter & Sorting Bar */}
      <div
        style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          padding: '12px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        }}
      >
        {/* Search Input */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '1 1 200px', maxWidth: '320px' }}>
          <Search size={16} color="#64748b" />
          <input
            type="text"
            placeholder="Search location in results..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 10px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.82rem',
            }}
          />
        </div>

        {/* Risk Filter Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', marginRight: '4px' }}>
            Filter:
          </span>
          <button
            type="button"
            onClick={() => setFilterRisk('ALL')}
            style={{
              background: filterRisk === 'ALL' ? '#0f172a' : '#f1f5f9',
              color: filterRisk === 'ALL' ? '#ffffff' : '#475569',
              border: 'none',
              borderRadius: '6px',
              padding: '5px 10px',
              fontSize: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            All ({spatialData?.points.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setFilterRisk('ELEVATED')}
            style={{
              background: filterRisk === 'ELEVATED' ? '#ea580c' : '#f1f5f9',
              color: filterRisk === 'ELEVATED' ? '#ffffff' : '#ea580c',
              border: 'none',
              borderRadius: '6px',
              padding: '5px 10px',
              fontSize: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Elevated Risk ({elevatedCount})
          </button>
          <button
            type="button"
            onClick={() => setFilterRisk('LOW')}
            style={{
              background: filterRisk === 'LOW' ? '#10b981' : '#f1f5f9',
              color: filterRisk === 'LOW' ? '#ffffff' : '#10b981',
              border: 'none',
              borderRadius: '6px',
              padding: '5px 10px',
              fontSize: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Low ({lowCount})
          </button>
          {abstainedCount > 0 && (
            <button
              type="button"
              onClick={() => setFilterRisk('ABSTAINED')}
              style={{
                background: filterRisk === 'ABSTAINED' ? '#64748b' : '#f1f5f9',
                color: filterRisk === 'ABSTAINED' ? '#ffffff' : '#64748b',
                border: 'none',
                borderRadius: '6px',
                padding: '5px 10px',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Abstained ({abstainedCount})
            </button>
          )}
        </div>

        {/* Sort & View Mode Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ArrowUpDown size={15} color="#64748b" />
            <select
              aria-label="Sort Locations"
              value={sortField}
              onChange={(e) => setSortField(e.target.value as SortField)}
              style={{
                padding: '5px 10px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#1e293b',
                background: '#f8fafc',
              }}
            >
              <option value="prob_desc">P(BUST): High to Low</option>
              <option value="prob_asc">P(BUST): Low to High</option>
              <option value="risk_desc">Risk Tier: Critical First</option>
              <option value="name_asc">Location: A to Z</option>
              <option value="input_order">Input Order</option>
            </select>
          </div>

          <div style={{ display: 'flex', border: '1px solid #cbd5e1', borderRadius: '6px', overflow: 'hidden' }}>
            <button
              type="button"
              onClick={() => setDisplayMode('cards')}
              title="Grid Cards View"
              style={{
                background: displayMode === 'cards' ? '#0284c7' : '#ffffff',
                color: displayMode === 'cards' ? '#ffffff' : '#64748b',
                border: 'none',
                padding: '6px 10px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <LayoutGrid size={15} />
            </button>
            <button
              type="button"
              onClick={() => setDisplayMode('table')}
              title="Dense Table View"
              style={{
                background: displayMode === 'table' ? '#0284c7' : '#ffffff',
                color: displayMode === 'table' ? '#ffffff' : '#64748b',
                border: 'none',
                padding: '6px 10px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <TableIcon size={15} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Layout: Grid/Table of Locations + Station Detail Panel */}
      <div
        className="multi-location-main-layout"
        style={{
          display: 'grid',
          gridTemplateColumns: selectedPoint ? 'minmax(0, 1.7fr) minmax(0, 1.1fr)' : '1fr',
          gap: '20px',
          alignItems: 'start',
        }}
      >
        {/* Left: Location Results (Cards or Table) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {displayMode === 'cards' ? (
            <div
              className="locations-card-grid"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: '14px',
              }}
            >
              {processedPoints.map((point, idx) => {
                const isSelected = selectedPoint?.location === point.location;
                const riskColor = getRiskColor(point.risk_level, point.abstain);
                const bustPercent =
                  point.bust_probability != null
                    ? `${(point.bust_probability * 100).toFixed(1)}%`
                    : 'N/A';

                return (
                  <div
                    key={`${point.location}-${idx}`}
                    data-testid={`location-card-${point.location}`}
                    onClick={() => setSelectedPoint(point)}
                    style={{
                      background: '#ffffff',
                      border: isSelected ? '2px solid #0284c7' : '1px solid #e2e8f0',
                      borderRadius: '10px',
                      padding: '16px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected
                        ? '0 4px 12px rgba(2, 132, 199, 0.15)'
                        : '0 1px 4px rgba(0,0,0,0.03)',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                    }}
                  >
                    <div>
                      {/* Card Header: Location Name & Risk Badge */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#0f172a' }}>
                            {point.resolved_name || point.location}
                          </div>
                          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '2px' }}>
                            {point.latitude != null && point.longitude != null
                              ? `${point.latitude.toFixed(2)}°N, ${point.longitude.toFixed(2)}°E`
                              : 'Coordinates unresolvable'}
                          </div>
                        </div>
                        <div>{getRiskBadge(point.risk_level, point.abstain)}</div>
                      </div>

                      {/* Probability Metric & Bar */}
                      <div style={{ marginTop: '14px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>
                            P(BUST)
                          </span>
                          <span style={{ fontSize: '1.35rem', fontWeight: 900, color: riskColor }}>
                            {bustPercent}
                          </span>
                        </div>

                        {/* Visual Risk Progress Bar */}
                        <div
                          style={{
                            width: '100%',
                            height: '6px',
                            background: '#f1f5f9',
                            borderRadius: '3px',
                            overflow: 'hidden',
                            marginTop: '6px',
                          }}
                        >
                          {point.bust_probability != null && (
                            <div
                              style={{
                                width: `${Math.min(100, Math.max(0, point.bust_probability * 100))}%`,
                                height: '100%',
                                background: riskColor,
                                borderRadius: '3px',
                              }}
                            />
                          )}
                        </div>
                      </div>

                      {/* Risk Drivers or Reason */}
                      <div style={{ marginTop: '12px' }}>
                        {point.dominant_risk_drivers && point.dominant_risk_drivers.length > 0 ? (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                            {point.dominant_risk_drivers.slice(0, 2).map((drv, dIdx) => (
                              <span
                                key={dIdx}
                                style={{
                                  background: '#f8fafc',
                                  color: '#475569',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  fontSize: '0.7rem',
                                  border: '1px solid #e2e8f0',
                                }}
                              >
                                {drv}
                              </span>
                            ))}
                          </div>
                        ) : point.abstain ? (
                          <span
                            style={{
                              color: '#ea580c',
                              fontSize: '0.72rem',
                              fontFamily: 'monospace',
                            }}
                          >
                            {point.reason_codes.join(', ') || 'ABSTAINED'}
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {/* Card Footer: Trust State & Detail Hint */}
                    <div
                      style={{
                        marginTop: '14px',
                        paddingTop: '10px',
                        borderTop: '1px solid #f1f5f9',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.75rem',
                      }}
                    >
                      <span style={{ color: '#64748b' }}>
                        Trust: <strong style={{ color: '#1e293b' }}>{point.trust_state}</strong>
                      </span>
                      <span style={{ color: '#0284c7', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '2px' }}>
                        Details <ChevronRight size={14} />
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* Table View */
            <div
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '10px',
                overflow: 'hidden',
                boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
              }}
            >
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                    <th style={{ padding: '10px 14px' }}>Location</th>
                    <th style={{ padding: '10px 14px' }}>Coordinates</th>
                    <th style={{ padding: '10px 14px' }}>P(BUST)</th>
                    <th style={{ padding: '10px 14px' }}>Risk Tier</th>
                    <th style={{ padding: '10px 14px' }}>Trust State</th>
                    <th style={{ padding: '10px 14px' }}>Dominant Driver</th>
                    <th style={{ padding: '10px 14px', textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {processedPoints.map((point, idx) => {
                    const isSelected = selectedPoint?.location === point.location;
                    const riskColor = getRiskColor(point.risk_level, point.abstain);
                    const bustPercent =
                      point.bust_probability != null
                        ? `${(point.bust_probability * 100).toFixed(1)}%`
                        : 'N/A';

                    return (
                      <tr
                        key={`${point.location}-${idx}`}
                        data-testid={`location-row-${point.location}`}
                        onClick={() => setSelectedPoint(point)}
                        style={{
                          borderBottom: '1px solid #f1f5f9',
                          background: isSelected ? '#f0f9ff' : idx % 2 === 0 ? '#ffffff' : '#fafafa',
                          cursor: 'pointer',
                        }}
                      >
                        <td style={{ padding: '10px 14px', fontWeight: 700, color: '#0f172a' }}>
                          {point.resolved_name || point.location}
                        </td>
                        <td style={{ padding: '10px 14px', color: '#64748b' }}>
                          {point.latitude != null && point.longitude != null
                            ? `${point.latitude.toFixed(2)}°, ${point.longitude.toFixed(2)}°`
                            : 'Unresolvable'}
                        </td>
                        <td style={{ padding: '10px 14px', fontWeight: 800, color: riskColor }}>
                          {bustPercent}
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          {getRiskBadge(point.risk_level, point.abstain)}
                        </td>
                        <td style={{ padding: '10px 14px', color: '#334155', fontWeight: 600 }}>
                          {point.trust_state}
                        </td>
                        <td style={{ padding: '10px 14px', color: '#64748b', fontSize: '0.75rem' }}>
                          {point.dominant_risk_drivers && point.dominant_risk_drivers[0]
                            ? point.dominant_risk_drivers[0]
                            : point.abstain
                            ? point.reason_codes[0] || 'ABSTAINED'
                            : 'N/A'}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedPoint(point);
                            }}
                            style={{
                              background: '#e0f2fe',
                              color: '#0369a1',
                              border: 'none',
                              borderRadius: '4px',
                              padding: '4px 8px',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {processedPoints.length === 0 && (
            <div
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '10px',
                padding: '36px',
                textAlign: 'center',
                color: '#64748b',
              }}
            >
              <Info size={24} color="#94a3b8" />
              <div style={{ fontWeight: 700, marginTop: '8px' }}>No Locations Match Current Filter</div>
              <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                Try selecting &apos;All&apos; or clearing your search term.
              </div>
            </div>
          )}
        </div>

        {/* Right: Selected Station Detail Inspector */}
        {selectedPoint && (
          <div
            className="station-inspector-card"
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '22px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
              position: 'sticky',
              top: '20px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                  Location Diagnostic Inspector
                </div>
                <h2 style={{ margin: '2px 0 0 0', fontSize: '1.3rem', fontWeight: 800, color: '#0f172a' }}>
                  {selectedPoint.resolved_name || selectedPoint.location}
                </h2>
                <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '2px' }}>
                  {selectedPoint.latitude != null && selectedPoint.longitude != null
                    ? `Coordinates: ${selectedPoint.latitude.toFixed(4)}°N, ${selectedPoint.longitude.toFixed(4)}°E`
                    : 'Coordinates unresolvable'}
                </div>
              </div>

              <div>{getRiskBadge(selectedPoint.risk_level, selectedPoint.abstain)}</div>
            </div>

            {/* Probability Metric Display */}
            <div
              style={{
                marginTop: '16px',
                background: selectedPoint.abstain ? '#f1f5f9' : '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '10px',
                padding: '14px 18px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b' }}>
                  CALIBRATED BUST PROBABILITY P(BUST)
                </div>
                <div
                  style={{
                    fontSize: '1.8rem',
                    fontWeight: 900,
                    color: getRiskColor(selectedPoint.risk_level, selectedPoint.abstain),
                    marginTop: '2px',
                  }}
                >
                  {selectedPoint.bust_probability != null
                    ? `${(selectedPoint.bust_probability * 100).toFixed(1)}%`
                    : 'ABSTAINED'}
                </div>
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Trust State</div>
                <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#1e293b' }}>
                  {selectedPoint.trust_state}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
                  {selectedPoint.calibration_status || 'CALIBRATED'}
                </div>
              </div>
            </div>

            {/* Diagnostic Metrics Matrix */}
            <div
              style={{
                marginTop: '16px',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '10px',
                fontSize: '0.8rem',
              }}
            >
              <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                <div style={{ color: '#64748b', fontSize: '0.72rem' }}>Variable</div>
                <div style={{ fontWeight: 700, color: '#0f172a' }}>{selectedPoint.variable}</div>
              </div>

              <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                <div style={{ color: '#64748b', fontSize: '0.72rem' }}>Forecast Lead</div>
                <div style={{ fontWeight: 700, color: '#0f172a' }}>
                  {selectedPoint.lead_hours}h ({selectedPoint.lead_days} days)
                </div>
              </div>

              <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                <div style={{ color: '#64748b', fontSize: '0.72rem' }}>Issue Cycle (UTC)</div>
                <div style={{ fontWeight: 600, color: '#0f172a' }}>
                  {selectedPoint.issue_time ? selectedPoint.issue_time.slice(0, 16).replace('T', ' ') : 'Live Operational'}
                </div>
              </div>

              <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                <div style={{ color: '#64748b', fontSize: '0.72rem' }}>Valid Target (UTC)</div>
                <div style={{ fontWeight: 600, color: '#0f172a' }}>
                  {selectedPoint.valid_time ? selectedPoint.valid_time.slice(0, 16).replace('T', ' ') : 'N/A'}
                </div>
              </div>

              {selectedPoint.confidence_index != null && (
                <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                  <div style={{ color: '#64748b', fontSize: '0.72rem' }}>Model Confidence</div>
                  <div style={{ fontWeight: 700, color: '#0f172a' }}>
                    {(selectedPoint.confidence_index * 100).toFixed(1)}%
                  </div>
                </div>
              )}

              {selectedPoint.uncertainty_pct != null && (
                <div style={{ background: '#f8fafc', padding: '8px 12px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                  <div style={{ color: '#64748b', fontSize: '0.72rem' }}>Ensemble Spread</div>
                  <div style={{ fontWeight: 700, color: '#0f172a' }}>
                    {selectedPoint.uncertainty_pct.toFixed(1)}%
                  </div>
                </div>
              )}
            </div>

            {/* Dominant Risk Drivers */}
            {selectedPoint.dominant_risk_drivers && selectedPoint.dominant_risk_drivers.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', marginBottom: '6px' }}>
                  DOMINANT PHYSICAL RISK DRIVERS
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {selectedPoint.dominant_risk_drivers.map((driver, dIdx) => (
                    <span
                      key={dIdx}
                      style={{
                        background: '#f1f5f9',
                        color: '#334155',
                        padding: '4px 9px',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      {driver}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Decision Guidance */}
            {selectedPoint.decision_guidance && (
              <div
                style={{
                  marginTop: '16px',
                  background: '#f0f9ff',
                  border: '1px solid #bae6fd',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  fontSize: '0.78rem',
                  color: '#0369a1',
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: '2px' }}>Operational Decision Guidance</div>
                <div>{selectedPoint.decision_guidance}</div>
              </div>
            )}

            {/* Cross-Link Action */}
            {onNavigateToSpatial && selectedPoint.latitude != null && (
              <div style={{ marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => onNavigateToSpatial(selectedPoint.resolved_name || selectedPoint.location)}
                  style={{
                    width: '100%',
                    background: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '9px 14px',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    cursor: 'pointer',
                  }}
                >
                  <ExternalLink size={15} />
                  <span>Highlight on Spatial Map</span>
                </button>
              </div>
            )}

            {onNavigateToDisagreement && (
              <div style={{ marginTop: '8px' }}>
                <button
                  type="button"
                  onClick={() => onNavigateToDisagreement(selectedPoint.resolved_name || selectedPoint.location, variable, leadHours)}
                  style={{
                    width: '100%',
                    background: '#6366f1',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '9px 14px',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    cursor: 'pointer',
                  }}
                >
                  <GitCompare size={15} />
                  <span>Inspect Forecast Disagreement</span>
                </button>
              </div>
            )}

            {/* Scientific Provenance */}
            <div
              style={{
                marginTop: '16px',
                padding: '10px 14px',
                background: isCertifiedScope ? '#f0fdf4' : '#fffbeb',
                border: `1px solid ${isCertifiedScope ? '#bbf7d0' : '#fde68a'}`,
                borderRadius: '8px',
                fontSize: '0.75rem',
                color: isCertifiedScope ? '#166534' : '#92400e',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <Info size={16} />
              <div>
                <strong>Model:</strong> {selectedPoint.model_version || 'v3_lightgbm_challenger'} |{' '}
                <strong>Scope:</strong>{' '}
                {selectedPoint.scientific_scope === 'FROZEN_BENCHMARK_LEAD_SCOPE'
                  ? 'Within Frozen Benchmark Lead Scope'
                  : 'Extended Operational Horizon'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MultiLocationPanel;
