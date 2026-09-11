import { Crosshair, Zap, Layers } from 'lucide-react';
import { BENCHMARK_LOCATIONS } from '../data/locations';

export default function LocationForm({
  location,
  setLocation,
  lat,
  setLat,
  lon,
  setLon,
  variable,
  setVariable,
  leadHorizon,
  setLeadHorizon,
  loading,
  onAudit,
  onSwitchToBatch,
}) {
  const handleLocationSelect = (selectedName) => {
    const target = BENCHMARK_LOCATIONS.find((l) => l.name === selectedName);
    if (target) {
      setLocation(target.name);
      setLat(target.lat);
      setLon(target.lon);
    }
  };

  return (
    <aside className="panel">
      <div className="panel-header">
        <span className="panel-title">
          <Crosshair size={16} /> Atmospheric Target
        </span>
        <span className="panel-badge">Issue-Time Safe</span>
      </div>

      {/* Benchmarked Calibrated Locations Dropdown */}
      <div className="form-group">
        <label>Location / Alias (Calibrated Domain)</label>
        <select
          value={location}
          onChange={(e) => handleLocationSelect(e.target.value)}
          style={{ fontWeight: 600, color: 'var(--noaa-dark-blue)' }}
        >
          <optgroup label="India Benchmark Grid (25 Calibrated Stations)">
            {BENCHMARK_LOCATIONS.map((loc) => (
              <option key={loc.name} value={loc.name}>
                {loc.name} ({loc.region}) — [{loc.lat.toFixed(2)}°, {loc.lon.toFixed(2)}°]
              </option>
            ))}
          </optgroup>
        </select>
      </div>

      {/* Coordinates Grid */}
      <div className="coord-grid form-group">
        <div>
          <label>Latitude</label>
          <input
            type="number"
            step="0.0001"
            value={lat}
            onChange={(e) => setLat(parseFloat(e.target.value) || 0)}
          />
        </div>
        <div>
          <label>Longitude</label>
          <input
            type="number"
            step="0.0001"
            value={lon}
            onChange={(e) => setLon(parseFloat(e.target.value) || 0)}
          />
        </div>
      </div>

      {/* Variable Selector */}
      <div className="form-group">
        <label>Atmospheric Variable</label>
        <select value={variable} onChange={(e) => setVariable(e.target.value)}>
          <option value="temperature_2m">2m Temperature (°C)</option>
          <option value="surface_pressure">Surface Pressure (hPa)</option>
          <option value="wind_speed_10m">10m Wind Speed (m/s)</option>
          <option value="precipitation">Precipitation Accumulation (mm)</option>
        </select>
      </div>

      {/* Lead Horizon Selector */}
      <div className="form-group">
        <label>Forecast Lead Horizon</label>
        <select value={leadHorizon} onChange={(e) => setLeadHorizon(e.target.value)}>
          <option value="24">24 Hours (Day 1 Operational)</option>
          <option value="48">48 Hours (Day 2 Synoptic)</option>
          <option value="72">72 Hours (Day 3 Medium-Range)</option>
          <option value="120">120 Hours (Day 5 Sub-Seasonal)</option>
        </select>
      </div>

      <button className="btn-primary" onClick={onAudit} disabled={loading}>
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
}
