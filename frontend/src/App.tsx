import React, { useEffect, useState } from 'react';
import { apiClient } from './api/client';
import {
  ApiError,
  HorizonTimelineRequest,
  HorizonTimelineResult,
  PredictionRequest,
  PredictionResponse,
} from './api/types';
import { AbstentionResult } from './components/AbstentionResult';
import { ErrorView } from './components/ErrorView';
import { ExplainabilityView } from './components/ExplainabilityView';
import { Footer } from './components/Footer';
import { ForecastForm } from './components/ForecastForm';
import { ForecastRiskTimeline } from './components/ForecastRiskTimeline';
import { Header } from './components/Header';
import { HorizonRiskDetails } from './components/HorizonRiskDetails';
import { PredictionResult } from './components/PredictionResult';

export const App: React.FC = () => {
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [serviceVersion, setServiceVersion] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeMode, setActiveMode] = useState<'single' | 'timeline'>('single');
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [timeline, setTimeline] = useState<HorizonTimelineResult | null>(null);
  const [selectedLeadHours, setSelectedLeadHours] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    // Initial health check
    apiClient.getHealth().then(({ data }) => {
      if (data && data.status === 'ok') {
        setIsBackendHealthy(true);
        setServiceVersion(data.version);
      } else {
        setIsBackendHealthy(false);
      }
    });
  }, []);

  const handleModeChange = (newMode: 'single' | 'timeline') => {
    setActiveMode(newMode);
    setError(null);
    if (newMode === 'single') {
      // Immediately clear timeline results and selected horizon on mode switch
      setTimeline(null);
      setSelectedLeadHours(null);
    } else {
      // Immediately clear single prediction results on mode switch
      setPrediction(null);
    }
  };

  const handleValidationError = (validationMsg: string) => {
    // Clear stale prediction and timeline states immediately on invalid submission attempt
    setPrediction(null);
    setTimeline(null);
    setSelectedLeadHours(null);
    setError({
      error: 'VALIDATION_ERROR',
      message: validationMsg,
      status_code: 422,
    });
  };

  const handleForecastSubmit = async (requestPayload: PredictionRequest) => {
    setIsLoading(true);
    setError(null);
    setPrediction(null);
    setTimeline(null);
    setSelectedLeadHours(null);

    const { data, error } = await apiClient.predictForecastBust(requestPayload);

    if (error) {
      setError(error);
      setPrediction(null);
    } else if (data) {
      setPrediction(data);
      setError(null);
    }

    setIsLoading(false);
  };

  const handleTimelineSubmit = async (requestPayload: HorizonTimelineRequest) => {
    setIsLoading(true);
    setError(null);
    setPrediction(null);
    setTimeline(null);
    setSelectedLeadHours(null);

    try {
      const result = await apiClient.predictHorizonTimeline(requestPayload);
      setTimeline(result);

      if (result.points.length > 0) {
        // Choose default selected horizon: point with highest probability, or first valid point
        const validPoints = result.points.filter(
          (p) => p.status === 'SUCCESS' && p.response?.bust_probability !== null
        );
        if (validPoints.length > 0) {
          const highestPoint = validPoints.reduce((prev, curr) =>
            (curr.response?.bust_probability || 0) > (prev.response?.bust_probability || 0) ? curr : prev
          );
          setSelectedLeadHours(highestPoint.lead_hours);
        } else {
          setSelectedLeadHours(result.points[0].lead_hours);
        }
      }
      setError(null);
    } catch (err: unknown) {
      setError({
        error: 'TIMELINE_EVALUATION_ERROR',
        message: err instanceof Error ? err.message : 'Failed to evaluate timeline risk trajectory.',
        status_code: 500,
      });
      setTimeline(null);
    }

    setIsLoading(false);
  };

  const handleSelectHorizon = (leadHours: number) => {
    setSelectedLeadHours(leadHours);
  };

  const selectedPoint =
    timeline && selectedLeadHours !== null
      ? timeline.points.find((p) => p.lead_hours === selectedLeadHours) || null
      : null;

  return (
    <div className="app-container">
      <Header isBackendHealthy={isBackendHealthy} serviceVersion={serviceVersion} />

      <main className="main-content" role="main">
        {/* Product Identity & Mission Banner */}
        <section className="hero-section">
          <div className="hero-badge">Medium-Range Forecast Sentinel</div>
          <h2 className="hero-heading">
            Anticipate Weather Forecast Failures Before They Happen
          </h2>
          <p className="hero-description">
            Veyra does <span className="hero-highlight">not</span> generate weather forecasts.
            Instead, it continuously evaluates issued numerical ensembles (NOAA GEFS) to estimate the probability that a forecast will fail unusually badly across horizons.
          </p>
        </section>

        {/* Dashboard 2-Column Grid */}
        <div className="dashboard-grid">
          {/* Left Column: Forecast Configuration Form */}
          <div className="form-column">
            <ForecastForm
              mode={activeMode}
              onModeChange={handleModeChange}
              onSubmit={handleForecastSubmit}
              onSubmitTimeline={handleTimelineSubmit}
              onValidationError={handleValidationError}
              isLoading={isLoading}
            />
          </div>

          {/* Right Column: Dynamic Results / Timeline / Abstention / Explanations */}
          <div className="results-column">
            {error && <ErrorView error={error} onDismiss={() => setError(null)} />}

            {isLoading && (
              <div className="glass-card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }} aria-busy="true">
                <div className="spinner" style={{ margin: '0 auto 1.5rem', width: '36px', height: '36px', borderWidth: '3px' }} />
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '0.5rem' }}>
                  {activeMode === 'timeline' ? 'Evaluating Forecast Trajectory' : 'Evaluating Forecast Ensemble'}
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '380px', margin: '0 auto' }}>
                  {activeMode === 'timeline'
                    ? 'Ingesting 31-member NOAA GEFS ensemble, calculating 26 issue-time physical features across horizons, and evaluating Platt-calibrated LightGBM inference...'
                    : 'Ingesting 31-member NOAA GEFS ensemble, calculating 26 issue-time physical features, and running Platt-calibrated LightGBM inference...'}
                </p>
              </div>
            )}

            {/* View A: Multi-Horizon Risk Timeline View (Active Mode = Timeline) */}
            {!isLoading && activeMode === 'timeline' && timeline && (
              <div className="results-container timeline-view-container">
                <ForecastRiskTimeline
                  timeline={timeline}
                  selectedLeadHours={selectedLeadHours}
                  onSelectHorizon={handleSelectHorizon}
                />

                {selectedPoint && (
                  <HorizonRiskDetails
                    point={selectedPoint}
                    location={timeline.location}
                    variable={timeline.variable}
                  />
                )}
              </div>
            )}

            {/* View B: Single Point-in-Time Prediction Result View (Active Mode = Single) */}
            {!isLoading && activeMode === 'single' && prediction && !prediction.abstain && (
              <div className="results-container">
                <PredictionResult prediction={prediction} />
                <ExplainabilityView explanation={prediction.explanation} />
              </div>
            )}

            {/* View C: Single Point Abstention View (Active Mode = Single) */}
            {!isLoading && activeMode === 'single' && prediction && prediction.abstain && (
              <div className="results-container">
                <AbstentionResult prediction={prediction} />
              </div>
            )}

            {/* View D: Initial Empty State Box */}
            {!isLoading && !error && ((activeMode === 'timeline' && !timeline) || (activeMode === 'single' && !prediction)) && (
              <div className="empty-state-box">
                <div className="empty-state-icon">📡</div>
                <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                  Sentinel Ready for Assessment
                </h3>
                <p className="empty-state-text">
                  {activeMode === 'timeline' ? (
                    <>
                      Enter a target city name or coordinates, choose a forecast variable and horizon window, then click{' '}
                      <strong style={{ color: 'var(--text-primary)' }}>Generate Risk Timeline</strong> to evaluate failure probabilities across horizons.
                    </>
                  ) : (
                    <>
                      Enter a target city name or geographical coordinate pair and click{' '}
                      <strong style={{ color: 'var(--text-primary)' }}>Estimate Bust Probability</strong> to inspect the reliability of the current forecast.
                    </>
                  )}
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      <Footer
        modelVersion={prediction?.model_version || (timeline?.points[0]?.response?.model_version) || 'prototype-gbm-v1'}
        dataVersion={prediction?.data_version || (timeline?.points[0]?.response?.data_version) || 'gefs-openmeteo-v1.0'}
      />
    </div>
  );
};

export default App;
