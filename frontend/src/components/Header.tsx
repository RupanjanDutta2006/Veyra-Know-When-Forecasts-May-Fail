import React from 'react';

interface HeaderProps {
  isBackendHealthy: boolean | null;
  serviceVersion?: string;
}

export const Header: React.FC<HeaderProps> = ({ isBackendHealthy, serviceVersion }) => {
  return (
    <header className="header-wrapper" role="banner">
      <div className="header-container">
        <a href="/" className="brand-section" aria-label="Veyra Home">
          <div className="brand-logo-icon" aria-hidden="true">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#ffffff"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
          </div>
          <div>
            <h1 className="brand-title">Veyra</h1>
            <div className="brand-tagline">Know When Forecasts May Fail</div>
          </div>
        </a>

        <div
          className="status-pill"
          role="status"
          aria-label={`Backend Status: ${
            isBackendHealthy === null
              ? 'Checking'
              : isBackendHealthy
              ? 'Online'
              : 'Offline'
          }`}
        >
          <span
            className={`status-dot ${isBackendHealthy === false ? 'offline' : ''}`}
          />
          <span>
            {isBackendHealthy === null
              ? 'Connecting...'
              : isBackendHealthy
              ? `API Online ${serviceVersion ? `v${serviceVersion}` : ''}`
              : 'Backend Offline'}
          </span>
        </div>
      </div>
    </header>
  );
};
