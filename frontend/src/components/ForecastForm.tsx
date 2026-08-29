import React, { useState } from 'react';
import { HorizonPreset, HorizonTimelineRequest, PredictionRequest, SupportedVariable } from '../api/types';

interface ForecastFormProps {
  mode?: 'single' | 'timeline';
  onModeChange?: (mode: 'single' | 'timeline') => void;
  onSubmit: (request: PredictionRequest) => void;
  onSubmitTimeline?: (request: HorizonTimelineRequest) => void;
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

export const ForecastForm: React.FC<ForecastFormProps> = ({
  mode = 'single',
  onModeChange,
  onSubmit,
  onSubmitTimeline,
  onValidationError,
  isLoading,
}) => {
  const [evaluationMode, setEvaluationMode] = useState<'single' | 'timeline'>(mode);
  const [location, setLocation] = useState<string>('London');
  const [variable, setVariable] = useState<SupportedVariable>('temperature_2m');
  const [issueTime, setIssueTime] = useState<string>('');
  const [validTime, setValidTime] = useState<string>('');
  const [preset, setPreset] = useState<HorizonPreset>('7_DAY');
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

  const handleModeChange = (newMode: 'single' | 'timeline') => {
    setEvaluationMode(newMode);
    setValidationError(null);
    onModeChange?.(newMode);
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

    let formattedIssueTime: string | undefined = undefined;
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

    if (evaluationMode === 'timeline') {
      if (onSubmitTimeline) {
        onSubmitTimeline({
          location: trimmedLocation,
          variable,
          issue_time: formattedIssueTime,
          preset,
        });
      }
      return;
    }

    // Single Target Forecast Validation
    let formattedValidTime: string | undefined = undefined;
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

      {/* Mode Switcher Tabs */}
      <div className="mode-toggle-group" role="tablist" aria-label="Evaluation Mode Selection">
        <button
          type="button"
          role="tab"
          aria-selected={evaluationMode === 'single'}
          className={`mode-tab-btn ${evaluationMode === 'single' ? 'active' : ''}`}
          onClick={() => handleModeChange('single')}
          disabled={isLoading}
        >
          Single Target Forecast
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={evaluationMode === 'timeline'}
          className={`mode-tab-btn ${evaluationMode === 'timeline' ? 'active' : ''}`}
          onClick={() => handleModeChange('timeline')}
          disabled={isLoading}
        >
          Visual Risk Timeline
        </button>
      </div>

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

        {/* Issue Time Input */}
        <div className="form-group">
          <label htmlFor="issue-time-input" className="form-label">
            Issue Time (UTC)
            <span className="form-hint">Optional cycle issuance (defaults to current cycle)</span>
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

        {/* Single Target Mode: Valid Time */}
        {evaluationMode === 'single' && (
          <div className="form-group">
            <label htmlFor="valid-time-input" className="form-label">
              Valid Target (UTC)
              <span className="form-hint">Optional valid timestamp (defaults to entire horizon)</span>
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
        )}

        {/* Timeline Mode: Preset Selection */}
        {evaluationMode === 'timeline' && (
          <div className="form-group">
            <label htmlFor="preset-select" className="form-label">
              Timeline Horizon Window
              <span className="form-hint">Forecast steps to evaluate</span>
            </label>
            <select
              id="preset-select"
              className="form-select"
              value={preset}
              onChange={(e) => setPreset(e.target.value as HorizonPreset)}
              disabled={isLoading}
            >
              <option value="7_DAY">Standard 7-Day Window (24h, 48h, 72h, 96h, 120h, 144h, 168h)</option>
              <option value="16_DAY">Full 16-Day Horizon (24h to 384h in 24h increments)</option>
            </select>
          </div>
        )}

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
              <span>
                {evaluationMode === 'timeline'
                  ? 'Evaluating Horizon Risk Trajectory...'
                  : 'Analyzing Forecast Ensemble...'}
              </span>
            </>
          ) : (
            <>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              <span>
                {evaluationMode === 'timeline'
                  ? 'Generate Risk Timeline'
                  : 'Estimate Bust Probability'}
              </span>
            </>
          )}
        </button>
      </form>
    </section>
  );
};
