import React, { useEffect, useState } from 'react';
import { apiClient } from './api/client';
import { ApiError, PredictionRequest, PredictionResponse } from './api/types';
import { AbstentionResult } from './components/AbstentionResult';
import { ErrorView } from './components/ErrorView';
import { ExplainabilityView } from './components/ExplainabilityView';
import { Footer } from './components/Footer';
import { ForecastForm } from './components/ForecastForm';
import { Header } from './components/Header';
import { PredictionResult } from './components/PredictionResult';

export const App: React.FC = () => {
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [serviceVersion, setServiceVersion] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
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

  const handleValidationError = (validationMsg: string) => {
    // Clear stale prediction state immediately on invalid submission attempt
    setPrediction(null);
    setError({
      error: 'VALIDATION_ERROR',
      message: validationMsg,
      status_code: 422,
    });
  };

  const handleForecastSubmit = async (requestPayload: PredictionRequest) => {
    setIsLoading(true);
    setError(null);
    setPrediction(null); // Clear stale prediction while new request is evaluating

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
            Instead, it continuously evaluates issued numerical ensembles (NOAA GEFS) to estimate the probability that a forecast will fail unusually badly.
          </p>
        </section>

        {/* Dashboard 2-Column Grid */}
        <div className="dashboard-grid">
          {/* Left Column: Forecast Configuration Form */}
          <div className="form-column">
            <ForecastForm
              onSubmit={handleForecastSubmit}
              onValidationError={handleValidationError}
              isLoading={isLoading}
            />
          </div>

          {/* Right Column: Dynamic Results / Abstention / Explanations */}
          <div className="results-column">
            {error && <ErrorView error={error} onDismiss={() => setError(null)} />}

            {isLoading && (
              <div className="glass-card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }} aria-busy="true">
                <div className="spinner" style={{ margin: '0 auto 1.5rem', width: '36px', height: '36px', borderWidth: '3px' }} />
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '0.5rem' }}>
                  Evaluating Forecast Ensemble
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '380px', margin: '0 auto' }}>
                  Ingesting 31-member NOAA GEFS ensemble, calculating 26 issue-time physical features, and running Platt-calibrated LightGBM inference...
                </p>
              </div>
            )}

            {!isLoading && prediction && !prediction.abstain && (
              <div className="results-container">
                <PredictionResult prediction={prediction} />
                <ExplainabilityView explanation={prediction.explanation} />
              </div>
            )}

            {!isLoading && prediction && prediction.abstain && (
              <div className="results-container">
                <AbstentionResult prediction={prediction} />
              </div>
            )}

            {!isLoading && !prediction && !error && (
              <div className="empty-state-box">
                <div className="empty-state-icon">📡</div>
                <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                  Sentinel Ready for Assessment
                </h3>
                <p className="empty-state-text">
                  Enter a target city name or geographical coordinate pair and click{' '}
                  <strong style={{ color: 'var(--text-primary)' }}>Estimate Bust Probability</strong> to inspect the reliability of the current forecast.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      <Footer
        modelVersion={prediction?.model_version || 'prototype-gbm-v1'}
        dataVersion={prediction?.data_version || 'gefs-openmeteo-v1.0'}
      />
    </div>
  );
};

export default App;
