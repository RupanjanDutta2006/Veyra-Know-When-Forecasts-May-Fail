import React, { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import {
  MapPin,
  AlertTriangle,
  Info,
  RefreshCw,
  Compass,
  AlertOctagon,
  SlidersHorizontal,
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
  { lead: 240, label: '240h (10 Days) [Benchmark Limit]', scope: 'FROZEN_BENCHMARK_LEAD_SCOPE' },
  { lead: 264, label: '264h (11 Days) [Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 288, label: '288h (12 Days) [Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 312, label: '312h (13 Days) [Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 336, label: '336h (14 Days) [Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 360, label: '360h (15 Days) [Operational]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
  { lead: 384, label: '384h (16 Days) [Max Horizon]', scope: 'EXTENDED_OPERATIONAL_HORIZON' },
];

function MapBoundsController({ points }: { points: SpatialReliabilityPoint[] }) {
  const map = useMap();
  useEffect(() => {
    const validPts = points.filter(
      (p) => p.latitude != null && p.longitude != null && !isNaN(p.latitude) && !isNaN(p.longitude)
    );
    if (validPts.length > 0) {
      if (validPts.length === 1) {
        map.setView([validPts[0].latitude!, validPts[0].longitude!], 6);
      } else {
        const bounds = validPts.map((p) => [p.latitude!, p.longitude!] as [number, number]);
        map.fitBounds(bounds, { padding: [40, 40] });
      }
    }
  }, [points, map]);
  return null;
}

interface SpatialReliabilityPanelProps {
  onNavigateToMultiLocation?: () => void;
}

export const SpatialReliabilityPanel: React.FC<SpatialReliabilityPanelProps> = ({ onNavigateToMultiLocation }) => {
  const [stationPreset, setStationPreset] = useState<'25_STATIONS' | 'METROS' | 'NORTH_SOUTH' | 'CUSTOM'>('25_STATIONS');
  const [customLocationsText, setCustomLocationsText] = useState<string>('Delhi, Kolkata, Mumbai, Chennai, Bengaluru');
  const [variable, setVariable] = useState<string>('temperature_2m');
  const [leadHours, setLeadHours] = useState<number>(24);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [spatialData, setSpatialData] = useState<SpatialReliabilityResponse | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<SpatialReliabilityPoint | null>(null);

  // Derive active location list based on preset
  const activeLocations = useMemo(() => {
    if (stationPreset === '25_STATIONS') return INDIAN_BENCHMARK_25_STATIONS;
    if (stationPreset === 'METROS') return MAJOR_METROS;
    if (stationPreset === 'NORTH_SOUTH') return NORTH_SOUTH;
    return customLocationsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }, [stationPreset, customLocationsText]);

  // Execute spatial reliability evaluation
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
        setError(apiError.message || 'Spatial evaluation request failed.');
        setSpatialData(null);
        setSelectedPoint(null);
      } else if (data) {
        setSpatialData(data);
        // Select first available point or first point
        const firstAvailable = data.points.find((p) => !p.abstain && p.bust_probability != null);
        setSelectedPoint(firstAvailable || data.points[0] || null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unexpected communication failure.');
    } finally {
      setLoading(false);
    }
  };

  // Evaluate on initial mount
  useEffect(() => {
    handleEvaluate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getRiskColor = (risk: RiskLevel | null, abstain: boolean) => {
    if (abstain || risk === null) return '#6b7280'; // neutral gray
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
        return '#6b7280';
    }
  };

  const getRiskBadge = (risk: RiskLevel | null, abstain: boolean) => {
    if (abstain || risk === null) {
      return (
        <span className="risk-badge" style={{ backgroundColor: '#4b5563', color: '#fff' }}>
          ABSTAINED
        </span>
      );
    }
    const color = getRiskColor(risk, false);
    return (
      <span className="risk-badge" style={{ backgroundColor: color, color: '#fff' }}>
        {risk} RISK
      </span>
    );
  };

  // Valid plottable points (with valid geographic coordinates)
  const plottablePoints = useMemo(() => {
    if (!spatialData) return [];
    return spatialData.points.filter(
      (p) => p.latitude != null && p.longitude != null && !isNaN(p.latitude) && !isNaN(p.longitude)
    );
  }, [spatialData]);

  // Points with unresolvable or null coordinates
  const unresolvablePoints = useMemo(() => {
    if (!spatialData) return [];
    return spatialData.points.filter(
      (p) => p.latitude == null || p.longitude == null || isNaN(p.latitude) || isNaN(p.longitude)
    );
  }, [spatialData]);

  const isCertifiedScope = leadHours <= 240;

  return (
    <div className="spatial-reliability-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner & Scientific Principles Notice */}
      <div
        className="spatial-header-card"
        style={{
          background: 'linear-gradient(135deg, #002b49 0%, #001e33 100%)',
          border: '1px solid #1e3a5f',
          borderRadius: '12px',
          padding: '20px 24px',
          color: '#ffffff',
          boxShadow: '0 4px 16px rgba(0, 43, 73, 0.25)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ background: '#0ea5e9', padding: '6px', borderRadius: '8px', display: 'flex' }}>
                <MapPin size={22} color="#ffffff" />
              </div>
              <h1 style={{ margin: 0, fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.01em' }}>
                Spatial Forecast Reliability Intelligence
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
              Evaluates discrete forecast-bust risk across authoritative meteorological stations using Veyra&apos;s frozen
              V3 LightGBM model and isotonic calibrator. <strong>No continuous surfaces or geographic interpolation:</strong> markers
              represent point-level forecast reliability intelligence, not weather severity.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {onNavigateToMultiLocation && (
              <button
                type="button"
                onClick={onNavigateToMultiLocation}
                style={{
                  background: '#1e293b',
                  color: '#c084fc',
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
                <SlidersHorizontal size={15} />
                <span>Multi-Location Matrix</span>
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
              {loading ? 'Evaluating...' : 'Refresh Spatial Intelligence'}
            </button>
          </div>
        </div>
      </div>

      {/* Control Bar: Variable, Horizon, Station Preset */}
      <div
        className="spatial-controls-card"
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
          <label htmlFor="station-preset-select" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
            Station Selection Preset
          </label>
          <select
            id="station-preset-select"
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
          <label htmlFor="spatial-variable-select" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
            Meteorological Variable
          </label>
          <select
            id="spatial-variable-select"
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
          <label htmlFor="spatial-horizon-select" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
            <span>Forecast Lead Horizon</span>
            <span style={{ color: isCertifiedScope ? '#059669' : '#d97706', fontWeight: 700 }}>
              {isCertifiedScope ? 'Within Benchmark Scope' : 'Extended Operational'}
            </span>
          </label>
          <select
            id="spatial-horizon-select"
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
          <label htmlFor="custom-locations-input" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
            Custom Location Queries (Comma-separated city names or coordinates)
          </label>
          <input
            id="custom-locations-input"
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

      {/* Error Notification */}
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
            <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>Spatial Query Alert</div>
            <div style={{ fontSize: '0.82rem', marginTop: '2px' }}>{error}</div>
          </div>
        </div>
      )}

      {/* Summary Metrics Bar */}
      {spatialData?.summary && (
        <div
          className="spatial-summary-grid"
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
              padding: '12px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>TOTAL EVALUATED</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
              {spatialData.summary.total_locations}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
              {spatialData.summary.available_locations} Available | {spatialData.summary.abstained_locations} Abstained
            </div>
          </div>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '12px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>PEAK P(BUST)</div>
            <div
              style={{
                fontSize: '1.4rem',
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
            <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
              {spatialData.summary.max_risk_location || 'None'}
            </div>
          </div>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '12px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>MEAN P(BUST)</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
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
              padding: '12px 16px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b' }}>ELEVATED RISK LOCATIONS</div>
            <div
              style={{
                fontSize: '1.4rem',
                fontWeight: 800,
                color: spatialData.summary.elevated_risk_locations > 0 ? '#ea580c' : '#10b981',
                marginTop: '4px',
              }}
            >
              {spatialData.summary.elevated_risk_locations}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>Medium, High, Critical</div>
          </div>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '12px 16px',
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

      {/* Main Spatial Layout: Map + Interactive Detail Panel */}
      <div
        className="spatial-main-layout"
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1.1fr)',
          gap: '20px',
        }}
      >
        {/* Left Column: Interactive Map */}
        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            minHeight: '520px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          }}
        >
          {/* Map Header */}
          <div
            style={{
              padding: '12px 18px',
              background: '#f8fafc',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Compass size={16} color="#0284c7" />
              <span>Discrete Evaluated Station Locations</span>
              <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 500 }}>
                ({plottablePoints.length} plotted)
              </span>
            </div>

            {/* Risk Legend */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.75rem', fontWeight: 600 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#10b981' }} /> Low
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b' }} /> Med
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444' }} /> High
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#8b5cf6' }} /> Crit
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#6b7280' }} /> Abstain
              </span>
            </div>
          </div>

          {/* Leaflet Map Canvas */}
          <div style={{ flex: 1, minHeight: '460px', position: 'relative' }}>
            <MapContainer
              center={[22.5, 80.0]}
              zoom={5}
              scrollWheelZoom={false}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapBoundsController points={plottablePoints} />

              {plottablePoints.map((point, idx) => {
                const isSelected = selectedPoint?.location === point.location;
                const riskColor = getRiskColor(point.risk_level, point.abstain);
                const lat = point.latitude!;
                const lon = point.longitude!;
                const bustPercent =
                  point.bust_probability != null
                    ? `${(point.bust_probability * 100).toFixed(1)}%`
                    : 'N/A';

                return (
                  <CircleMarker
                    key={`${point.location}-${idx}`}
                    center={[lat, lon]}
                    radius={isSelected ? 10 : 7}
                    pathOptions={{
                      fillColor: riskColor,
                      color: isSelected ? '#ffffff' : '#1e293b',
                      weight: isSelected ? 3 : 1.5,
                      fillOpacity: 0.9,
                    }}
                    eventHandlers={{
                      click: () => setSelectedPoint(point),
                    }}
                  >
                    <Popup>
                      <div style={{ minWidth: '160px', padding: '2px' }}>
                        <div style={{ fontWeight: 800, fontSize: '0.92rem', color: '#0f172a' }}>
                          {point.resolved_name || point.location}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px' }}>
                          [{lat.toFixed(4)}°, {lon.toFixed(4)}°]
                        </div>
                        <hr style={{ margin: '6px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginTop: '4px' }}>
                          <span style={{ color: '#64748b' }}>P(BUST):</span>
                          <span style={{ fontWeight: 800, color: riskColor }}>{bustPercent}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginTop: '2px' }}>
                          <span style={{ color: '#64748b' }}>Risk Tier:</span>
                          <span style={{ fontWeight: 700 }}>{point.risk_level || 'ABSTAINED'}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginTop: '2px' }}>
                          <span style={{ color: '#64748b' }}>Trust:</span>
                          <span style={{ fontWeight: 600 }}>{point.trust_state}</span>
                        </div>
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          </div>
        </div>

        {/* Right Column: Station Detail Card & Abstention Drawer */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Selected Station Intelligence Card */}
          {selectedPoint ? (
            <div
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                padding: '20px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                    Station Intelligence
                  </div>
                  <h2 style={{ margin: '2px 0 0 0', fontSize: '1.25rem', fontWeight: 800, color: '#0f172a' }}>
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

              {/* Point Probability Metric Box */}
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

              {/* Parameter & Model Metadata Grid */}
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
              </div>

              {/* Physical Risk Drivers */}
              {selectedPoint.dominant_risk_drivers && selectedPoint.dominant_risk_drivers.length > 0 && (
                <div style={{ marginTop: '14px' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', marginBottom: '6px' }}>
                    DOMINANT RISK DRIVERS
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {selectedPoint.dominant_risk_drivers.map((driver, dIdx) => (
                      <span
                        key={dIdx}
                        style={{
                          background: '#f1f5f9',
                          color: '#334155',
                          padding: '3px 8px',
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

              {/* Reason Codes if any */}
              {selectedPoint.reason_codes && selectedPoint.reason_codes.length > 0 && (
                <div style={{ marginTop: '12px' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', marginBottom: '4px' }}>
                    REASON CODES
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {selectedPoint.reason_codes.map((rc, rcIdx) => (
                      <span
                        key={rcIdx}
                        style={{
                          background: '#e2e8f0',
                          color: '#1e293b',
                          padding: '2px 7px',
                          borderRadius: '4px',
                          fontSize: '0.72rem',
                          fontFamily: 'monospace',
                        }}
                      >
                        {rc}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Scientific Provenance Note */}
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
          ) : (
            <div
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                padding: '36px 20px',
                textAlign: 'center',
                color: '#64748b',
              }}
            >
              <Info size={24} color="#94a3b8" />
              <div style={{ fontWeight: 700, marginTop: '8px' }}>No Location Selected</div>
              <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                Click any marker on the map to inspect its discrete forecast reliability diagnostics.
              </div>
            </div>
          )}

          {/* Unresolvable / Abstained Points Drawer */}
          {unresolvablePoints.length > 0 && (
            <div
              style={{
                background: '#fff7ed',
                border: '1px solid #ffedd5',
                borderRadius: '12px',
                padding: '14px 18px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#c2410c', fontWeight: 700, fontSize: '0.85rem' }}>
                <AlertTriangle size={16} />
                <span>Unresolvable / Abstained Locations ({unresolvablePoints.length})</span>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#9a3412', marginTop: '4px' }}>
                Not plotted on map (no valid geographic coordinates). Never plotted at (0, 0).
              </div>
              <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {unresolvablePoints.map((pt, uIdx) => (
                  <div
                    key={uIdx}
                    style={{
                      background: '#ffffff',
                      border: '1px solid #fed7aa',
                      borderRadius: '6px',
                      padding: '6px 10px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.78rem',
                    }}
                  >
                    <span style={{ fontWeight: 700, color: '#1e293b' }}>{pt.location}</span>
                    <span style={{ color: '#ea580c', fontFamily: 'monospace', fontSize: '0.72rem' }}>
                      {pt.reason_codes.join(', ') || 'INVALID_LOCATION'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SpatialReliabilityPanel;
