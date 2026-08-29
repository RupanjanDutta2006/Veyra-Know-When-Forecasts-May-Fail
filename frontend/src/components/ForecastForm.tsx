import React, { useState } from 'react';
import { PredictionRequest, SupportedVariable } from '../api/types';

interface ForecastFormProps {
  onSubmit: (request: PredictionRequest) => void;
  onValidationError?: (errorMessage: string) => void;
  isLoading: boolean;
}

const SUPPORTED_VARIABLES: { value: SupportedVariable; label: string }[] = [
  { value: 'temperature_2m', label: '2m Temperature (°C)' },
  { value: 'surface_pressure', label: 'Surface Pressure (hPa)' },
  { value: 'wind_speed_10m', label: '10m Wind Speed (m/s)' },
  { value: 'relative_humidity_2m', label: '2m Relative Humidity (%)' },
  { value: 'precipitation', label: 'Total Precipitation (mm)' },
];

const QUICK_LOCATIONS = [
  'London',
  'Delhi',
  'Kolkata',
  'Mumbai',
  'Tokyo',
  'Dubai',
  '22.5726, 88.3639',
];

function formatToIsoUtc(datetimeStr: string): string {
  const trimmed = datetimeStr.trim();
  if (!trimmed) return '';
  if (trimmed.endsWith('Z')) return trimmed;
  const parts = trimmed.split('T');
  if (parts.length === 2) {
    const datePart = parts[0];
    const timePart = parts[1].length === 5 ? `${parts[1]}:00` : parts[1];
    return `${datePart}T${timePart}Z`;
  }
  return new Date(trimmed).toISOString();
}

export const ForecastForm: React.FC<ForecastFormProps> = ({ onSubmit, onValidationError, isLoading }) => {
  const [location, setLocation] = useState<string>('London');
  const [variable, setVariable] = useState<SupportedVariable>('temperature_2m');
  const [issueTime, setIssueTime] = useState<string>('');
  const [validTime, setValidTime] = useState<string>('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleQuickLocation = (loc: string) => {
    setLocation(loc);
    setValidationError(null);
  };

  const handleLocationChange = (val: string) => {
    setLocation(val);
    setValidationError(null);
  };

  const handleVariableChange = (val: SupportedVariable) => {
    setVariable(val);
    setValidationError(null);
  };

  const handleIssueTimeChange = (val: string) => {
    setIssueTime(val);
    setValidationError(null);
  };

  const handleValidTimeChange = (val: string) => {
    setValidTime(val);
    setValidationError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const trimmedLocation = location.trim();
    if (!trimmedLocation) {
      const msg = 'Please enter a valid location or geographic coordinate pair.';
      setValidationError(msg);
      onValidationError?.(msg);
      return;
    }

    // Optional Datetime Lead Validation
    let formattedIssueTime: string | undefined = undefined;
    let formattedValidTime: string | undefined = undefined;

    if (issueTime) {
      const isoIssue = formatToIsoUtc(issueTime);
      const dIssue = new Date(isoIssue);
      if (isNaN(dIssue.getTime())) {
        const msg = 'Issue time is invalid.';
        setValidationError(msg);
        onValidationError?.(msg);
        return;
      }
      formattedIssueTime = isoIssue;
    }

    if (validTime) {
      const isoValid = formatToIsoUtc(validTime);
      const dValid = new Date(isoValid);
      if (isNaN(dValid.getTime())) {
        const msg = 'Valid time is invalid.';
        setValidationError(msg);
        onValidationError?.(msg);
        return;
      }
      formattedValidTime = isoValid;
    }

    if (formattedIssueTime && formattedValidTime) {
      const dIssue = new Date(formattedIssueTime);
      const dValid = new Date(formattedValidTime);
      const leadHours = (dValid.getTime() - dIssue.getTime()) / (1000 * 60 * 60);

      if (leadHours <= 0) {
        const msg = 'Forecast valid time must be strictly after the forecast issue time.';
        setValidationError(msg);
        onValidationError?.(msg);
        return;
      }

      if (leadHours > 384) {
        const msg = 'Forecast horizon cannot exceed 384 hours (16 days).';
        setValidationError(msg);
        onValidationError?.(msg);
        return;
      }
    }

    const requestPayload: PredictionRequest = {
      location: trimmedLocation,
      variable,
      ...(formattedIssueTime ? { issue_time: formattedIssueTime } : {}),
      ...(formattedValidTime ? { valid_time: formattedValidTime } : {}),
    };

    onSubmit(requestPayload);
  };

  return (
    <section className="glass-card" aria-labelledby="form-heading">
      <h2 id="form-heading" className="card-title">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--accent-cyan)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
        Evaluate Forecast Reliability
      </h2>
      <p className="card-subtitle">
        Assess the probability that an existing medium-range weather forecast will significantly fail.
      </p>

      {!onValidationError && validationError && (
        <div className="error-banner" role="alert">
          <div className="error-desc">{validationError}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        {/* Location Input */}
        <div className="form-group">
          <label htmlFor="location-input" className="form-label">
            Location or Coordinates
            <span className="form-hint">City name or "lat, lon"</span>
          </label>
          <div className="input-wrapper">
            <span className="input-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
            </span>
            <input
              id="location-input"
              type="text"
              className="form-input has-icon"
              placeholder="e.g. London, Tokyo, Siliguri or 22.5726, 88.3639"
              value={location}
              onChange={(e) => handleLocationChange(e.target.value)}
              disabled={isLoading}
              required
              aria-required="true"
            />
          </div>
          <div className="quick-locations" aria-label="Suggested Benchmark Locations">
            {QUICK_LOCATIONS.map((loc) => (
              <button
                key={loc}
                type="button"
                className="quick-loc-btn"
                onClick={() => handleQuickLocation(loc)}
                disabled={isLoading}
              >
                {loc}
              </button>
            ))}
          </div>
        </div>

        {/* Forecast Variable Selection */}
        <div className="form-group">
          <label htmlFor="variable-select" className="form-label">
            Meteorological Variable
            <span className="form-hint">Target physical variable</span>
          </label>
          <select
            id="variable-select"
            className="form-select"
            value={variable}
            onChange={(e) => handleVariableChange(e.target.value as SupportedVariable)}
            disabled={isLoading}
          >
            {SUPPORTED_VARIABLES.map((v) => (
              <option key={v.value} value={v.value}>
                {v.label}
              </option>
            ))}
          </select>
        </div>

        {/* Optional Cycle Timestamps */}
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="issue-time-input" className="form-label">
              Issue Time (UTC)
              <span className="form-hint">Optional cycle issuance</span>
            </label>
            <input
              id="issue-time-input"
              type="datetime-local"
              className="form-input"
              value={issueTime}
              onChange={(e) => handleIssueTimeChange(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="valid-time-input" className="form-label">
              Valid Target (UTC)
              <span className="form-hint">Optional valid timestamp</span>
            </label>
            <input
              id="valid-time-input"
              type="datetime-local"
              className="form-input"
              value={validTime}
              onChange={(e) => handleValidTimeChange(e.target.value)}
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          className="submit-btn"
          disabled={isLoading || !location.trim()}
          aria-busy={isLoading}
        >
          {isLoading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <span>Analyzing Forecast Ensemble...</span>
            </>
          ) : (
            <>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              <span>Estimate Bust Probability</span>
            </>
          )}
        </button>
      </form>
    </section>
  );
};
