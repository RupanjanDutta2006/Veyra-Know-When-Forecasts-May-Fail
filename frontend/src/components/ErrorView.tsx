import React from 'react';
import { ApiError } from '../api/types';

interface ErrorViewProps {
  error: ApiError | null;
  onDismiss?: () => void;
}

export const ErrorView: React.FC<ErrorViewProps> = ({ error, onDismiss }) => {
  if (!error) return null;

  const isRateLimited = error.status_code === 429 || error.error === 'RATE_LIMIT_EXCEEDED';
  const retryAfter = error.retry_after_seconds;

  let title = 'Request Error';
  if (isRateLimited) {
    title = 'API Rate Limit Exceeded';
  } else if (error.status_code === 422 || error.error === 'VALIDATION_ERROR') {
    title = 'Input Validation Error';
  } else if (error.error === 'NETWORK_ERROR') {
    title = 'Network Connection Failed';
  }

  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      <div style={{ flexShrink: 0, marginTop: '2px', color: '#ef4444' }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>

      <div style={{ flex: 1 }}>
        <div className="error-title">{title}</div>
        <div className="error-desc">
          {error.message || 'An unexpected error occurred while communicating with the sentinel service.'}
        </div>

        {/* 429 Retry-After Notice */}
        {isRateLimited && retryAfter && (
          <div style={{ marginTop: '0.4rem', fontWeight: 600, color: '#fef08a' }}>
            Please wait approximately {retryAfter} second{retryAfter > 1 ? 's' : ''} before submitting another analysis request.
          </div>
        )}

        {/* Validation Errors detail list */}
        {Array.isArray(error.detail) && error.detail.length > 0 && (
          <ul style={{ marginTop: '0.5rem', paddingLeft: '1.2rem', fontSize: '0.8rem' }}>
            {error.detail.map((d, idx) => (
              <li key={idx}>
                {d.loc ? `${d.loc.join('.')}: ` : ''}
                {d.msg || JSON.stringify(d)}
              </li>
            ))}
          </ul>
        )}

        {/* Correlation Request ID for Support / Diagnostics */}
        {error.request_id && (
          <div className="error-meta">
            Correlation ID: <code>{error.request_id}</code>
          </div>
        )}
      </div>

      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          style={{
            background: 'none',
            border: 'none',
            color: '#fca5a5',
            cursor: 'pointer',
            padding: '4px',
          }}
          aria-label="Dismiss error"
        >
          ✕
        </button>
      )}
    </div>
  );
};
