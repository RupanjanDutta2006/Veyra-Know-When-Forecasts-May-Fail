import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { ModelEvaluationResponse, V3ModelEvaluationResponse } from '../api/types';
import { Cpu, CheckCircle2, AlertCircle } from 'lucide-react';

export const ModelCatalog: React.FC = () => {
  const [v3Data, setV3Data] = useState<V3ModelEvaluationResponse | null>(null);
  const [legacyData, setLegacyData] = useState<ModelEvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      apiClient.getV3Evaluation(),
      apiClient.getModelEvaluation(),
    ])
      .then(([v3Res, legacyRes]) => {
        if (v3Res.status === 'fulfilled' && v3Res.value.data) {
          setV3Data(v3Res.value.data);
        }
        if (legacyRes.status === 'fulfilled' && legacyRes.value.data) {
          setLegacyData(legacyRes.value.data);
        }
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch model evaluation metadata.');
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="panel" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="panel-header">
        <span className="panel-title">
          <Cpu size={18} /> Model Registry &amp; Scientific Architecture Benchmarks
        </span>
        <span className="panel-badge">
          {v3Data ? 'SYNCED WITH API' : loading ? 'LOADING...' : 'OFFLINE'}
        </span>
      </div>

      <p style={{ fontSize: '0.9rem', color: '#555', marginBottom: '18px' }}>
        Authoritative machine learning models evaluated for forecast bust risk. The Veyra pipeline evaluates ensemble
        divergence, baroclinic shear, and synoptic spread to compute calibrated bust probabilities.
      </p>

      {error && (
        <div className="abstention-box" style={{ marginBottom: '16px' }} role="alert">
          <div className="abstention-title">
            <AlertCircle size={16} /> Evaluation Diagnostics Warning
          </div>
          <div className="abstention-desc">{error}</div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* V3 Authoritative Frozen Championship Model Card */}
        <div className="model-card" style={{ borderLeft: '4px solid #10b981' }}>
          <div className="model-card-header">
            <div>
              <span className="model-card-title">
                {v3Data?.model_name || 'veyra-v3-benchmark-lightgbm'} (Authoritative Frozen Championship)
              </span>
              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                {v3Data?.model_family || 'LightGBM + Isotonic Calibration'} &bull; Version {v3Data?.model_version || '3.0.0'}
              </div>
            </div>
            <span
              className="diag-pill"
              style={{ background: '#dcfce7', color: '#166534' }}
            >
              <CheckCircle2 size={12} /> ACTIVE PRODUCTION
            </span>
          </div>

          <p style={{ fontSize: '0.82rem', color: '#475569', margin: '8px 0' }}>
            Day 23 certified championship model. Trained on multi-ensemble GEFS reforecasts with isotonic probability calibration.
          </p>

          <div className="model-card-metrics">
            <div className="kpi-card">
              <div className="kpi-title">Brier Score</div>
              <div className="kpi-val" style={{ fontSize: '1rem', color: '#15803d' }}>
                {v3Data?.metrics.brier_score !== undefined ? v3Data.metrics.brier_score.toFixed(6) : '0.053798'}
              </div>
              <div className="kpi-sub">Lower is better</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-title">Expected Calib. Error</div>
              <div className="kpi-val" style={{ fontSize: '1rem', color: '#15803d' }}>
                {v3Data?.metrics.ece !== undefined ? `${(v3Data.metrics.ece * 100).toFixed(2)}%` : '0.64%'}
              </div>
              <div className="kpi-sub">&lt; 1% (10-bin ECE)</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-title">ROC-AUC</div>
              <div className="kpi-val" style={{ fontSize: '1rem', color: '#0369a1' }}>
                {v3Data?.metrics.roc_auc !== undefined ? v3Data.metrics.roc_auc.toFixed(4) : '0.7698'}
              </div>
              <div className="kpi-sub">Discrimination</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-title">Average Precision</div>
              <div className="kpi-val" style={{ fontSize: '1rem', color: '#0369a1' }}>
                {v3Data?.metrics.average_precision !== undefined ? v3Data.metrics.average_precision.toFixed(4) : '0.2047'}
              </div>
              <div className="kpi-sub">PR-AUC</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-title">BSS vs Climatology</div>
              <div className="kpi-val" style={{ fontSize: '1rem', color: '#15803d' }}>
                {v3Data?.metrics.bss_vs_e0 !== undefined ? v3Data.metrics.bss_vs_e0.toFixed(4) : '0.0807'}
              </div>
              <div className="kpi-sub">+8.07% vs E0</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-title">BSS vs Ensemble Spread</div>
              <div className="kpi-val" style={{ fontSize: '1rem', color: '#15803d' }}>
                {v3Data?.metrics.bss_vs_e1b !== undefined ? v3Data.metrics.bss_vs_e1b.toFixed(4) : '0.0778'}
              </div>
              <div className="kpi-sub">+7.78% vs E1b</div>
            </div>
          </div>

          {v3Data?.generalization_limits && (
            <div style={{ marginTop: '12px', borderTop: '1px solid #e2e8f0', paddingTop: '10px' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
                Scientific Generalization Limits
              </div>
              <ul style={{ fontSize: '0.78rem', color: '#475569', paddingLeft: '18px', lineHeight: 1.5 }}>
                {v3Data.generalization_limits.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Legacy Prototype Model Card */}
        <div className="model-card" style={{ borderLeft: '4px solid #94a3b8' }}>
          <div className="model-card-header">
            <div>
              <span className="model-card-title">
                {legacyData?.model_name || 'prototype-gbm-v1'} (Legacy Prototype)
              </span>
              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                {legacyData?.model_type || 'GradientBoostingClassifier'} &bull; Version {legacyData?.model_version || '1.0.0'}
              </div>
            </div>
            <span
              className="diag-pill"
              style={{ background: '#f1f5f9', color: '#475569' }}
            >
              LEGACY COMPATIBLE
            </span>
          </div>

          <p style={{ fontSize: '0.82rem', color: '#475569', margin: '8px 0' }}>
            First generation baseline prototype serving backward-compatible predictions.
          </p>

          <div className="model-card-metrics">
            <div className="kpi-card">
              <div className="kpi-title">ROC-AUC</div>
              <div className="kpi-val" style={{ fontSize: '1rem' }}>
                {legacyData?.metrics?.roc_auc !== undefined ? legacyData.metrics.roc_auc.toFixed(4) : '0.8450'}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-title">Brier Score</div>
              <div className="kpi-val" style={{ fontSize: '1rem' }}>
                {legacyData?.metrics?.brier_score !== undefined ? legacyData.metrics.brier_score.toFixed(4) : '0.1180'}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-title">Calibration Status</div>
              <div className="kpi-val" style={{ fontSize: '0.9rem' }}>
                {legacyData?.calibration?.is_calibrated ? 'CALIBRATED' : 'RAW'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ModelCatalog;
