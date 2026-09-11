import React from 'react';
import { ShieldAlert } from 'lucide-react';

interface AgencyBannerProps {
  isBackendHealthy: boolean | null;
  utcTime: string;
}

export const AgencyBanner: React.FC<AgencyBannerProps> = ({ isBackendHealthy, utcTime }) => {
  return (
    <header className="agency-banner" role="banner">
      <div className="brand-group">
        <ShieldAlert className="brand-icon" aria-hidden="true" />
        <span className="brand-title">VEYRA SENTINEL</span>
        <span className="brand-subtitle">Atmospheric Forecast Reliability Platform</span>
        <span className="release-tag">v3.0.0-frozen</span>
      </div>
      <div className="header-status-group">
        <span className="status-badge" role="status" aria-label="Gateway Status">
          <span
            className={`status-dot ${isBackendHealthy === true ? '' : 'offline'}`}
            aria-hidden="true"
          />
          <span>{isBackendHealthy === true ? 'GATEWAY LIVE' : isBackendHealthy === false ? 'GATEWAY OFFLINE' : 'CHECKING GATEWAY...'}</span>
        </span>
        <span className="status-badge">
          <span style={{ color: '#ffd200' }}>ROLE: OPERATIONAL</span>
        </span>
        <span className="status-badge">
          <span>UTC:</span> <span className="mono">{utcTime || '--:--:--'}</span>
        </span>
      </div>
    </header>
  );
};

export default AgencyBanner;
