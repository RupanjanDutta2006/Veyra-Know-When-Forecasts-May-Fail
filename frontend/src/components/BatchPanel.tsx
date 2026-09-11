import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { INDIAN_BENCHMARK_25_STATIONS } from '../data/locations';
import { MultiLocationPredictionItemResult } from '../api/types';
import {
  Layers,
  Play,
  AlertCircle,
  Search,
  Loader2,
  Trash2,
} from 'lucide-react';

const DEFAULT_25_TEXT = INDIAN_BENCHMARK_25_STATIONS.join('\n');

export const EVALUATION_VARIABLES = [
  { id: 'temperature_2m', label: '2m Temperature', unit: '°C' },
  { id: 'surface_pressure', label: 'Surface Pressure', unit: 'hPa' },
  { id: 'wind_speed_10m', label: '10m Wind Speed', unit: 'm/s' },
];

export const BatchPanel: React.FC = () => {
  const [rawInput, setRawInput] = useState(DEFAULT_25_TEXT);
  const [variable, setVariable] = useState('temperature_2m');
  const [results, setResults] = useState<MultiLocationPredictionItemResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState('');
  const [filterRisk, setFilterRisk] = useState('ALL');

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (loading) {
      setElapsedSeconds(0);
      timer = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [loading]);

  const locationList = rawInput
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);

  const handleLoadAll25 = () => {
    setRawInput(DEFAULT_25_TEXT);
    setError(null);
  };

  const handleClear = () => {
    setRawInput('');
    setResults([]);
    setError(null);
  };

  async function handleBatchSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (locationList.length === 0) {
      setError('Please provide at least one station or coordinate.');
      return;
    }

    setLoading(true);
    setError(null);

    const varsToRun =
      variable === 'ALL'
        ? EVALUATION_VARIABLES
        : [EVALUATION_VARIABLES.find((v) => v.id === variable) || { id: variable, label: variable, unit: '' }];

    try {
      let combined: MultiLocationPredictionItemResult[] = [];

      for (const v of varsToRun) {
        const { data, error: apiErr } = await apiClient.predictBatch({
          locations: locationList,
          variable: v.id,
        });

        if (apiErr) {
          setError(`Batch failed: ${apiErr.message || apiErr.error}`);
        } else if (data && data.results) {
          combined.push(...data.results);
        }
      }

      setResults(combined);
    } catch (err: any) {
      setError(`Network error executing batch: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  // Filter results
  const filteredResults = results.filter((item) => {
    const loc = (item.input_location || item.response?.location || '').toLowerCase();
    const matchesQuery = loc.includes(filterQuery.toLowerCase());
    const isAbstain = item.response?.abstain || item.response?.bust_probability === null;
    const risk = isAbstain ? 'ABSTAIN' : item.response?.risk_level || 'LOW';
    const matchesRisk = filterRisk === 'ALL' || risk === filterRisk;
    return matchesQuery && matchesRisk;
  });

  return (
    <section className="panel" style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div className="panel-header">
        <span className="panel-title">
          <Layers size={18} /> Synoptic Batch Evaluation (Multi-Station)
        </span>
        <span className="panel-badge">
          {results.length > 0 ? `${results.length} Evaluated` : 'Standby'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '20px' }}>
        {/* Left: Input Form */}
        <div>
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <label htmlFor="batch-locations">Target Locations ({locationList.length})</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={handleLoadAll25}
                  style={{ background: 'none', border: 'none', color: 'var(--noaa-accent)', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 600 }}
                >
                  Reset 25
                </button>
                <span style={{ color: '#cbd5e1' }}>|</span>
                <button
                  type="button"
                  onClick={handleClear}
                  style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '2px' }}
                >
                  <Trash2 size={10} /> Clear
                </button>
              </div>
            </div>
            <textarea
              id="batch-locations"
              rows={10}
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              placeholder="Enter station names or lat,lon coordinates (one per line)"
              style={{ fontFamily: 'JetBrains Mono', fontSize: '0.82rem' }}
            />
          </div>

          <div className="form-group">
            <label htmlFor="batch-variable">Target Variable</label>
            <select
              id="batch-variable"
              value={variable}
              onChange={(e) => setVariable(e.target.value)}
            >
              <option value="temperature_2m">2m Temperature (°C)</option>
              <option value="surface_pressure">Surface Pressure (hPa)</option>
              <option value="wind_speed_10m">10m Wind Speed (m/s)</option>
              <option value="ALL">All 3 Certified Variables (Sequential)</option>
            </select>
          </div>

          <button
            type="button"
            className="btn-primary"
            onClick={() => handleBatchSubmit()}
            disabled={loading || locationList.length === 0}
          >
            {loading ? (
              <>
                <Loader2 size={16} className="spin" />
                <span>Auditing Batch... ({elapsedSeconds}s)</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>Execute Batch Evaluation</span>
              </>
            )}
          </button>
        </div>

        {/* Right: Results Table */}
        <div>
          {error && (
            <div className="abstention-box" style={{ marginBottom: '12px' }} role="alert">
              <div className="abstention-title">
                <AlertCircle size={16} /> Batch Evaluation Error
              </div>
              <div className="abstention-desc">{error}</div>
            </div>
          )}

          {/* Table Filters */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '12px', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '160px', position: 'relative' }}>
              <input
                type="text"
                placeholder="Filter by station name..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                style={{ paddingLeft: '32px', height: '36px', minHeight: '36px', fontSize: '0.85rem' }}
              />
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '11px', color: '#64748b' }} />
            </div>
            <select
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value)}
              style={{ width: '140px', height: '36px', minHeight: '36px', fontSize: '0.85rem' }}
            >
              <option value="ALL">All Risk Tiers</option>
              <option value="LOW">LOW Risk</option>
              <option value="MEDIUM">MEDIUM Risk</option>
              <option value="HIGH">HIGH Risk</option>
              <option value="CRITICAL">CRITICAL Risk</option>
              <option value="ABSTAIN">ABSTAINED</option>
            </select>
          </div>

          {/* Results Table */}
          <div className="table-wrapper" style={{ maxHeight: '420px', overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Station</th>
                  <th>Bust Probability</th>
                  <th>Risk Tier</th>
                  <th>Trust State</th>
                  <th>Reason Codes</th>
                </tr>
              </thead>
              <tbody>
                {filteredResults.length > 0 ? (
                  filteredResults.map((item, idx) => {
                    const resp = item.response;
                    const isAbstain = resp?.abstain || resp?.bust_probability === null;
                    const prob = resp?.bust_probability !== null && resp?.bust_probability !== undefined
                      ? `${(resp.bust_probability * 100).toFixed(2)}%`
                      : 'ABSTAINED';

                    return (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600, color: 'var(--noaa-dark-blue)' }}>
                          {item.input_location || resp?.location}
                        </td>
                        <td style={{ fontWeight: 700 }}>
                          {prob}
                        </td>
                        <td>
                          <span
                            className="diag-pill"
                            style={{
                              background: isAbstain ? '#fee2e2' : resp?.risk_level === 'CRITICAL' ? '#fee2e2' : resp?.risk_level === 'HIGH' ? '#ffedd5' : resp?.risk_level === 'MEDIUM' ? '#fef3c7' : '#dcfce7',
                              color: isAbstain ? '#991b1b' : resp?.risk_level === 'CRITICAL' ? '#991b1b' : resp?.risk_level === 'HIGH' ? '#c2410c' : resp?.risk_level === 'MEDIUM' ? '#b45309' : '#15803d',
                            }}
                          >
                            {isAbstain ? 'ABSTAIN' : resp?.risk_level || 'LOW'}
                          </span>
                        </td>
                        <td>{resp?.trust_state || 'UNAVAILABLE'}</td>
                        <td style={{ fontSize: '0.72rem', color: '#64748b' }}>
                          {resp?.reason_codes?.join(', ') || 'SUCCESS'}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                      {loading ? 'Executing batch evaluation against Veyra backend...' : 'No batch results. Click "Execute Batch Evaluation" to audit stations.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
};

export default BatchPanel;
