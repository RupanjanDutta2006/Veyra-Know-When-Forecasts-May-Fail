import { ShieldAlert } from 'lucide-react';

export default function AgencyBanner({ isBackendHealthy, utcTime }) {
  return (
    <header className="agency-banner">
      <div className="brand-group">
        <ShieldAlert className="brand-icon" />
        <span className="brand-title">VEYRA SENTINEL</span>
        <span className="brand-subtitle">Atmospheric Forecast Reliability Platform</span>
        <span className="release-tag">v4.0.0-rc1</span>
      </div>
      <div className="header-status-group">
        <span className="status-badge">
          <span className={`status-dot ${isBackendHealthy ? '' : 'offline'}`} />
          <span>{isBackendHealthy ? 'GATEWAY LIVE' : 'GATEWAY OFFLINE (DEMO)'}</span>
        </span>
        <span className="status-badge">
          <span style={{ color: '#ffd200' }}>ROLE: USER</span>
        </span>
        <span className="status-badge">
          <span>UTC:</span> <span className="mono">{utcTime || '--:--:--'}</span>
        </span>
      </div>
    </header>
  );
}
