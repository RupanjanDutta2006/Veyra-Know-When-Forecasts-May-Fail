import React from 'react';

interface FooterProps {
  modelVersion?: string | null;
  dataVersion?: string | null;
}

export const Footer: React.FC<FooterProps> = ({
  modelVersion = 'prototype-gbm-v1',
  dataVersion = 'gefs-openmeteo-v1.0',
}) => {
  return (
    <footer className="footer-wrapper" role="contentinfo">
      <div className="footer-container">
        <div>
          <strong>Veyra</strong> — Forecast-Bust Sentinel AI Platform
          <div style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>
            Evaluates issued numerical weather forecasts to estimate the probability of significant forecast failure.
          </div>
        </div>

        <div className="footer-meta-group">
          <div className="footer-meta-item">
            Model: <strong>{modelVersion || 'prototype-gbm-v1'}</strong>
          </div>
          <div className="footer-meta-item">
            Ensemble: <strong>{dataVersion || 'NOAA GEFS 31-member'}</strong>
          </div>
          <div className="footer-meta-item">
            Threshold: <strong>0.280 (Platt Calibrated)</strong>
          </div>
          <div className="footer-meta-item">
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--accent-cyan)', textDecoration: 'none' }}
            >
              API Docs →
            </a>

          </div>
        </div>
      </div>
    </footer>
  );
};
