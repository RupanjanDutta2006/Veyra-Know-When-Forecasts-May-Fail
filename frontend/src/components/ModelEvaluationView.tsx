import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { V3ModelEvaluationResponse } from '../api/types';

export const ModelEvaluationView: React.FC = () => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [data, setData] = useState<V3ModelEvaluationResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && !data && !isLoading) {
      setIsLoading(true);
      setError(null);
      apiClient.getV3Evaluation().then(({ data: evalData, error: apiErr }) => {
        setIsLoading(false);
        if (apiErr) {
          setError(apiErr.message || 'Failed to load V3 evaluation diagnostics.');
        } else if (evalData) {
          setData(evalData);
        }
      });
    }
  }, [isOpen, data, isLoading]);

  return (
    <div className="glass-card" style={{ marginTop: '1.5rem' }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'none',
          border: 'none',
          color: 'var(--text-primary)',
          cursor: 'pointer',
          padding: '0.25rem 0',
          fontFamily: 'var(--font-display)',
          fontSize: '1.05rem',
          fontWeight: 600,
        }}
        aria-expanded={isOpen}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>🔬</span> Model Evaluation &amp; Scientific Diagnostics
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 500,
              padding: '0.15rem 0.5rem',
              borderRadius: '4px',
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              color: 'var(--accent-cyan)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
            }}
          >
            Frozen Historical Benchmark
          </span>
        </span>
        <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>
          {isOpen ? '▲ Collapse' : '▼ View Diagnostics'}
        </span>
      </button>

      {isOpen && (
        <div style={{ marginTop: '1.25rem', borderTop: '1px solid var(--border-glass)', paddingTop: '1rem' }}>
          {isLoading && (
            <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-muted)' }}>
              Loading frozen V3 championship evaluation...
            </div>
          )}

          {error && (
            <div style={{ padding: '0.75rem', color: 'var(--risk-critical)', fontSize: '0.9rem' }}>
              ⚠️ {error}
            </div>
          )}

          {data && (
            <div>
              {/* Context banner */}
              <div
                style={{
                  backgroundColor: 'rgba(245, 158, 11, 0.1)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  borderRadius: '6px',
                  padding: '0.75rem 1rem',
                  marginBottom: '1rem',
                  fontSize: '0.85rem',
                  color: 'var(--text-secondary)',
                }}
              >
                <strong style={{ color: '#f59e0b' }}>Caveat:</strong> These metrics reflect the{' '}
                <strong>Frozen Historical Benchmark (2017–2019 / 25 canonical stations)</strong> evaluated under
                strict chronological holdout. They do not represent live operational accuracy.
              </div>

              {/* Model metadata summary */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: '0.75rem',
                  marginBottom: '1.25rem',
                  fontSize: '0.85rem',
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Model Version:</span>{' '}
                  <strong>{data.model_version}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Family:</span>{' '}
                  <strong>{data.model_family}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Feature Count:</span>{' '}
                  <strong>{data.feature_count} features</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Calibration:</span>{' '}
                  <strong>{data.calibration_method}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Evaluation Period:</span>{' '}
                  <strong>{data.evaluation_period}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Test Samples:</span>{' '}
                  <strong>{data.test_samples.toLocaleString()} ({data.test_cycles} cycles)</strong>
                </div>
              </div>

              {/* Scalar Benchmark Metrics Grid */}
              <h4
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--text-secondary)',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '0.75rem',
                }}
              >
                Frozen Test Metrics (Calibrated V3 vs Baselines)
              </h4>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                  gap: '0.75rem',
                  marginBottom: '1.25rem',
                }}
              >
                <div className="metric-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-glass)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Average Precision (AP)</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                    {data.metrics.average_precision.toFixed(4)}
                  </div>
                </div>

                <div className="metric-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-glass)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>PR-AUC (Trapezoidal)</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                    {data.metrics.pr_auc_trapezoidal.toFixed(4)}
                  </div>
                </div>

                <div className="metric-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-glass)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ROC-AUC</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {data.metrics.roc_auc.toFixed(4)}
                  </div>
                </div>

                <div className="metric-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-glass)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Brier Score</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {data.metrics.brier_score.toFixed(6)}
                  </div>
                </div>

                <div className="metric-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-glass)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>BSS vs Climatology (E0)</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#10b981' }}>
                    {`+${data.metrics.bss_vs_e0.toFixed(4)}`}
                  </div>
                </div>

                <div className="metric-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-glass)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>BSS vs Raw Spread (E1b)</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#10b981' }}>
                    {`+${data.metrics.bss_vs_e1b.toFixed(4)}`}
                  </div>
                </div>

                <div className="metric-box" style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-glass)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ECE (Expected Calib. Error)</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {data.metrics.ece.toFixed(4)}
                  </div>
                </div>
              </div>

              {/* Generalization Limits */}
              {data.generalization_limits && data.generalization_limits.length > 0 && (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-glass)', paddingTop: '0.75rem' }}>
                  <strong style={{ color: 'var(--text-secondary)' }}>Generalization Boundaries:</strong>
                  <ul style={{ margin: '0.5rem 0 0 1.25rem', padding: 0 }}>
                    {data.generalization_limits.map((limit, idx) => (
                      <li key={idx} style={{ marginBottom: '0.25rem' }}>{limit}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
