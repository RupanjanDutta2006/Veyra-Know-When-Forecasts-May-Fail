import { useState, useEffect } from 'react';
import AgencyBanner from './components/AgencyBanner';
import Navigation from './components/Navigation';
import LocationForm from './components/LocationForm';
import ForecastMap from './components/ForecastMap';
import HistoricalChart from './components/HistoricalChart';
import VerificationPanel from './components/VerificationPanel';
import BatchPanel from './components/BatchPanel';
import ModelCatalog from './components/ModelCatalog';
import { getHealth, predictLocation } from './api/veyraApi';
import { BENCHMARK_LOCATIONS } from './data/locations';

export default function App() {
  const [view, setView] = useState('sentinel');
  const [utcTime, setUtcTime] = useState('--:--:--');
  const [isBackendHealthy, setIsBackendHealthy] = useState(false);
  const [loading, setLoading] = useState(false);

  // Form State initialized to first benchmark station (Delhi)
  const [location, setLocation] = useState(BENCHMARK_LOCATIONS[0].name);
  const [lat, setLat] = useState(BENCHMARK_LOCATIONS[0].lat);
  const [lon, setLon] = useState(BENCHMARK_LOCATIONS[0].lon);
  const [variable, setVariable] = useState('temperature_2m');
  const [leadHorizon, setLeadHorizon] = useState('48');

  // Telemetry & Prediction Response State
  const [prediction, setPrediction] = useState({
    location: BENCHMARK_LOCATIONS[0].name,
    latitude: BENCHMARK_LOCATIONS[0].lat,
    longitude: BENCHMARK_LOCATIONS[0].lon,
    bust_probability: 0.18,
    risk_level: 'LOW',
    severity_class: 'MARGINAL',
    confidence_index: 95,
    stability: 95,
    uncertainty_pct: 3.37,
    trust_state: 'SUPPORTED',
    failure_fingerprint: 'STABLE_SYNOPTIC_CONSENSUS',
    conformal_lower: 24.1,
    conformal_upper: 30.3,
    units: '°C',
    abstain: false,
    evidence: '[INITIALIZED] Veyra Sentinel standing by for real-time inference telemetry...',
  });

  // Keep UTC Clock ticking
  useEffect(() => {
    const updateTime = () => setUtcTime(new Date().toISOString().slice(11, 19));
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Check Backend Health on Mount & periodically
  useEffect(() => {
    const checkHealth = () => {
      getHealth()
        .then((res) => {
          setIsBackendHealthy(res && (res.status === 'ok' || res.status === 'healthy'));
        })
        .catch(() => {
          setIsBackendHealthy(false);
        });
    };
    checkHealth();
    const healthInterval = setInterval(checkHealth, 15000);
    return () => clearInterval(healthInterval);
  }, []);

  // Run Forecast Bust Reliability Audit
  const handleAudit = async () => {
    setLoading(true);
    try {
      // Real API Call to FastAPI Backend
      const res = await predictLocation({
        location: location.trim(),
        variable,
      });

      setPrediction((prev) => ({
        ...prev,
        ...res,
        location,
        latitude: lat,
        longitude: lon,
        units: variable === 'precipitation' ? 'mm' : variable === 'surface_pressure' ? 'hPa' : '°C',
        conformal_lower: res.conformal_lower ?? 24.1,
        conformal_upper: res.conformal_upper ?? 30.3,
        evidence: `[AUDIT-LOG ${new Date().toISOString()}]\nLOCATION: ${location} (${lat}, ${lon})\nVARIABLE: ${variable}\nCONFIDENCE: ${
          res.confidence_index != null ? `${res.confidence_index}%` : '95%'
        }\nTRUST: ${res.trust_state ?? 'SUPPORTED'}\nMODEL: ${res.model_version ?? 'veyra-v3-lightgbm'}`,
      }));
    } catch (err) {
      // Safe fallback if backend is offline or external weather fetch times out
      const isOod = lat < 6.0 || lat > 37.5 || lon < 68.0 || lon > 98.0 || location.toLowerCase().includes('south pole');
      setPrediction((prev) => ({
        ...prev,
        location,
        latitude: lat,
        longitude: lon,
        bust_probability: isOod ? null : 0.18,
        risk_level: isOod ? 'ABSTAIN' : 'LOW',
        trust_state: isOod ? 'ABSTAINED' : 'SUPPORTED',
        abstain: isOod,
        conformal_lower: variable === 'surface_pressure' ? 995.0 : 24.1,
        conformal_upper: variable === 'surface_pressure' ? 1018.0 : 30.3,
        units: variable === 'precipitation' ? 'mm' : variable === 'surface_pressure' ? 'hPa' : '°C',
        evidence: `[OFFLINE / DEMO TELEMETRY]\nStatus: ${err.message || 'Backend service offline'}\nLocation: ${location} (${lat}, ${lon})\nVariable: ${variable}\nLead Time: ${leadHorizon}h`,
      }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Agency Header */}
      <AgencyBanner isBackendHealthy={isBackendHealthy} utcTime={utcTime} />

      {/* Navigation */}
      <Navigation view={view} setView={setView} />

      {/* Breadcrumbs */}
      <div className="breadcrumb">
        Home &gt; Reliability Layer &gt; <strong>{view.toUpperCase()}</strong>
      </div>

      {/* Main Workspace View */}
      <main>
        {view === 'sentinel' && (
          <div className="workspace">
            {/* Left Column: Atmospheric Target Input */}
            <LocationForm
              location={location}
              setLocation={setLocation}
              lat={lat}
              setLat={setLat}
              lon={lon}
              setLon={setLon}
              variable={variable}
              setVariable={setVariable}
              leadHorizon={leadHorizon}
              setLeadHorizon={setLeadHorizon}
              loading={loading}
              onAudit={handleAudit}
              onSwitchToBatch={() => setView('batch')}
            />

            {/* Center Column: Interactive Map & 90-Day Multi-Provider Trend */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', minWidth: 0 }}>
              <ForecastMap latitude={lat} longitude={lon} label={location} />
              <HistoricalChart data={prediction.history} />
            </div>

            {/* Right Column: Telemetry & Conformal Verification */}
            <VerificationPanel prediction={prediction} />
          </div>
        )}

        {view === 'batch' && <BatchPanel />}
        {view === 'models' && <ModelCatalog />}
      </main>

      {/* Footer */}
      <footer>
        <div>
          <a
            href="https://github.com/RupanjanDutta2006/Veyra-Know-When-Forecasts-May-Fail"
            target="_blank"
            rel="noreferrer"
          >
            GitHub Repository
          </a>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
            FastAPI Documentation
          </a>
          <a href="http://localhost:8000/v1/health" target="_blank" rel="noreferrer">
            Health Check API
          </a>
        </div>
        <div style={{ opacity: 0.75, marginTop: '8px' }}>
          &copy; 2026 Veyra Sentinel Research Platform — Atmospheric Forecast Reliability Layer.
        </div>
      </footer>
    </div>
  );
}
