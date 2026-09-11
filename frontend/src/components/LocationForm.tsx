import React from 'react';
import { Crosshair, Zap, Layers, Search } from 'lucide-react';
import { BENCHMARK_LOCATIONS } from '../data/locations';
import { DashboardMode } from '../api/types';

interface LocationFormProps {
  location: string;
  setLocation: (loc: string) => void;
  lat: number;
  setLat: (lat: number) => void;
  lon: number;
  setLon: (lon: number) => void;
  variable: string;
  setVariable: (v: string) => void;
  mode: DashboardMode;
  setMode: (m: DashboardMode) => void;
  loading: boolean;
  onAudit: () => void;
  onSwitchToBatch?: () => void;
}

export const LocationForm: React.FC<LocationFormProps> = ({
  location,
  setLocation,
  lat,
  setLat,
  lon,
  setLon,
  variable,
  setVariable,
  mode,
  setMode,
  loading,
  onAudit,
  onSwitchToBatch,
}) => {
  const handlePresetSelect = (selectedName: string) => {
    const target = BENCHMARK_LOCATIONS.find((l) => l.name === selectedName);
    if (target) {
      setLocation(target.name);
      setLat(target.lat);
      setLon(target.lon);
    }
  };

  const handleCoordinateChange = (newLat: number, newLon: number) => {
    setLat(newLat);
    setLon(newLon);
    // If coordinates are set directly, update location query to coordinate format
    if (!isNaN(newLat) && !isNaN(newLon)) {
      setLocation(`${newLat.toFixed(4)}, ${newLon.toFixed(4)}`);
    }
  };

  return (
    <aside className="panel" aria-label="Atmospheric Target Configuration">
      <div className="panel-header">
        <span className="panel-title">
          <Crosshair size={16} /> Atmospheric Target
        </span>
        <span className="panel-badge">Issue-Time Safe</span>
      </div>

      {/* Preset Station Dropdown */}
      <div className="form-group">
        <label htmlFor="preset-select">Preset Station / Synoptic Hub</label>
        <select
          id="preset-select"
          value={BENCHMARK_LOCATIONS.some((l) => l.name.toLowerCase() === location.trim().toLowerCase()) ? location : ''}
          onChange={(e) => {
            if (e.target.value) handlePresetSelect(e.target.value);
          }}
          style={{ fontWeight: 600, color: 'var(--noaa-dark-blue)' }}
        >
          <option value="">-- Select Synoptic Station (or type below) --</option>
          <optgroup label="India Benchmark Grid (25 Calibrated Stations)">
            {BENCHMARK_LOCATIONS.map((loc) => (
              <option key={loc.name} value={loc.name}>
                {loc.name} ({loc.region}) — [{loc.lat.toFixed(2)}°, {loc.lon.toFixed(2)}°]
              </option>
            ))}
          </optgroup>
        </select>
      </div>

      {/* Free-text Location / Search Input */}
      <div className="form-group">
        <label htmlFor="location-input">Location Name or Coordinates</label>
        <div style={{ position: 'relative' }}>
          <input
            id="location-input"
            type="text"
            placeholder="e.g. Kolkata, Delhi, 22.57,88.36"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            style={{ paddingLeft: '34px', fontFamily: 'inherit' }}
          />
          <Search
            size={16}
            style={{
              position: 'absolute',
              left: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--noaa-muted)',
              pointerEvents: 'none',
            }}
          />
        </div>
      </div>

      {/* Coordinates Grid */}
      <div className="coord-grid form-group">
        <div>
          <label htmlFor="lat-input">Latitude</label>
          <input
            id="lat-input"
            type="number"
            step="0.0001"
            value={lat}
            onChange={(e) => handleCoordinateChange(parseFloat(e.target.value) || 0, lon)}
          />
        </div>
        <div>
          <label htmlFor="lon-input">Longitude</label>
          <input
            id="lon-input"
            type="number"
            step="0.0001"
            value={lon}
            onChange={(e) => handleCoordinateChange(lat, parseFloat(e.target.value) || 0)}
          />
        </div>
      </div>

      {/* Variable Selector */}
      <div className="form-group">
        <label htmlFor="var-select">Target Meteorological Variable</label>
        <select
          id="var-select"
          value={variable}
          onChange={(e) => setVariable(e.target.value)}
        >
          <option value="temperature_2m">2m Temperature (°C) [Certified Benchmark]</option>
          <option value="surface_pressure">Surface Pressure (hPa) [Certified Benchmark]</option>
          <option value="wind_speed_10m">10m Wind Speed (m/s) [Certified Benchmark]</option>
        </select>
      </div>

      {/* Forecast Evaluation Mode Selector */}
      <div className="form-group">
        <label htmlFor="mode-select">Evaluation Horizon Mode</label>
        <select
          id="mode-select"
          value={mode}
          onChange={(e) => setMode(e.target.value as DashboardMode)}
          style={{ fontWeight: 600 }}
        >
          <option value="single">Single (24h Canonical Operational Lead)</option>
          <option value="standard_7d">Standard 7 Day (24h–168h Multi-Horizon)</option>
          <option value="full_16d">Full 16 Day (24h–384h Synoptic Extension)</option>
        </select>
      </div>

      <button
        type="button"
        className="btn-primary"
        onClick={onAudit}
        disabled={loading || !location.trim()}
      >
        <Zap size={16} /> {loading ? 'Auditing Reliability...' : 'Audit Reliability'}
      </button>

      {/* Quick Access to 25-Station Batch Evaluation */}
      <div
        style={{
          marginTop: '16px',
          padding: '12px',
          background: 'rgba(0, 55, 100, 0.04)',
          border: '1px dashed rgba(0, 55, 100, 0.25)',
          borderRadius: '6px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--noaa-dark-blue)', marginBottom: '6px' }}>
          Multi-Station Operations
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => onSwitchToBatch && onSwitchToBatch()}
          style={{
            width: '100%',
            fontSize: '0.82rem',
            padding: '8px 12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}
        >
          <Layers size={14} /> Run All 25 Stations in Batch
        </button>
      </div>
    </aside>
  );
};

export default LocationForm;
