import React from 'react';
import { CrossProviderDisagreementResponse } from '../api/types';

interface CrossProviderDisagreementPanelProps {
  data?: CrossProviderDisagreementResponse | null;
  isLoading?: boolean;
}

export const CrossProviderDisagreementPanel: React.FC<CrossProviderDisagreementPanelProps> = ({
  data,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-slate-400 animate-pulse">
        <div className="h-6 w-64 bg-slate-800 rounded mb-4"></div>
        <div className="h-20 bg-slate-800/50 rounded"></div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-slate-400">
        <h3 className="text-lg font-semibold text-slate-200 mb-2">Cross-Provider Disagreement</h3>
        <p className="text-sm">No cross-provider comparison data available.</p>
      </div>
    );
  }

  const {
    status,
    canonical_location,
    variable,
    unit,
    primary_provider,
    secondary_provider,
    absolute_difference,
    signed_difference,
    relative_difference_pct,
    has_fixture_provider,
    provenance_notice,
    scope_note,
  } = data;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl text-slate-200 space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <span>🌐</span> Cross-Provider Forecast Difference
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Diagnostic comparison between normalized provider forecast values for{' '}
            <span className="text-slate-200 font-medium">{canonical_location}</span> ({variable})
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${
            status === 'AVAILABLE'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
          }`}
        >
          {status}
        </span>
      </div>

      {/* Fixture Provenance Banner */}
      {has_fixture_provider && (
        <div className="bg-sky-950/40 border border-sky-800/60 rounded-lg p-3 text-xs text-sky-300 flex items-start gap-2.5">
          <span className="text-sky-400 text-base">ℹ️</span>
          <div>
            <p className="font-semibold text-sky-200">Secondary Provider: Deterministic Fixture Data</p>
            <p className="mt-0.5 text-sky-300/90">{provenance_notice}</p>
          </div>
        </div>
      )}

      {/* Provider Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Primary Provider */}
        <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Primary Provider
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300">
              {primary_provider?.provider_source_mode || 'LIVE'}
            </span>
          </div>
          <p className="text-sm font-medium text-white">{primary_provider?.provider_name || 'Primary'}</p>
          <div className="text-2xl font-extrabold text-emerald-400">
            {primary_provider?.forecast_value !== null && primary_provider?.forecast_value !== undefined
              ? `${primary_provider.forecast_value} ${unit}`
              : 'Unavailable'}
          </div>
        </div>

        {/* Secondary Provider */}
        <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Secondary Provider
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300">
              {secondary_provider?.provider_source_mode || 'FIXTURE'}
            </span>
          </div>
          <p className="text-sm font-medium text-white">{secondary_provider?.provider_name || 'Secondary'}</p>
          <div className="text-2xl font-extrabold text-sky-400">
            {secondary_provider?.forecast_value !== null && secondary_provider?.forecast_value !== undefined
              ? `${secondary_provider.forecast_value} ${unit}`
              : 'Unavailable'}
          </div>
        </div>
      </div>

      {/* Difference Metrics */}
      {status === 'AVAILABLE' && absolute_difference !== null && (
        <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-4 grid grid-cols-3 gap-3 text-center">
          <div>
            <div className="text-xs text-slate-400 uppercase font-medium mb-1">Absolute Difference</div>
            <div className="text-lg font-bold text-amber-400">
              {absolute_difference} {unit}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-medium mb-1">Signed Difference</div>
            <div className="text-lg font-bold text-slate-200">
              {signed_difference && signed_difference > 0 ? `+${signed_difference}` : signed_difference} {unit}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-medium mb-1">Relative Difference</div>
            <div className="text-lg font-bold text-slate-300">
              {relative_difference_pct !== null ? `${relative_difference_pct}%` : 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* Scientific Scope Disclaimer */}
      <div className="border-t border-slate-800/60 pt-3 text-[11px] text-slate-500 leading-relaxed">
        <span className="font-semibold text-slate-400">Scientific Scope Note: </span>
        {scope_note}
      </div>
    </div>
  );
};
