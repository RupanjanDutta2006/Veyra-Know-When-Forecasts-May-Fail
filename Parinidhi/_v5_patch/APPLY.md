# Forecast-Bust Sentinel — Data Foundation v4 patch

This patch replaces the missing/broken historical ingestion layer with real NOAA GEFSv12 reforecast + ERA5 verification ingestion.

## Apply

1. Extract this ZIP into the root of `forecast-bust-sentinel` and choose **Replace** for existing files.
2. Keep the existing `scratch/env_eccodes` environment.
3. From the repo root, run:

```powershell
conda run -p .\\scratch\\env_eccodes python -m pytest tests/test_noaa_reforecast_foundation.py -q
```

4. Then run a real single-run smoke test:

```powershell
conda run -p .\\scratch\\env_eccodes python -c "from ingestion.historical_gefs_collector import HistoricalGEFSCollector; df,m=HistoricalGEFSCollector().collect_run('2017-03-14T00:00:00Z',22.5726,88.3639,'kolkata',horizon_hours=12,step_hours=3); print(df[['issue_time','valid_time','lead_hours','variable','value','ensemble_mean','ensemble_std','member_count','member_ids','grid_latitude','grid_longitude','spatial_distance_km']].head(20).to_string(index=False)); print('MEMBERS:',m['member_codes'])"
```

This uses the exact NOAA 2017-03-14 00Z GEFSv12 reforecast run and preserves actual c00/p01... member values.

## Important scientific changes

- Historical GEFSv12 reforecast is explicitly **00Z once daily**, not falsely treated as 00/06/12/18 operational coverage.
- Normal reforecast runs have **5 members** (`c00`, `p01`-`p04`); weekly extended runs expose **11** (`c00`, `p01`-`p10`). The code discovers the actual member directories rather than assuming a fixed count.
- Exact `issue_time` is always the model initialization time; it is never inferred from `valid_time[0]`.
- Actual NOAA grid coordinates and requested-to-grid spatial distance are preserved.
- Individual member values are retained in a sidecar manifest (`member_values_json` and run manifest) while the existing summary schema remains compatible.
- ERA5 is explicitly a **verification/reanalysis reference**, not station ground truth.
- The old hard-coded ERA5 availability date was removed.
- Historical validation no longer rejects legitimate 5-member GEFSv12 reforecast runs merely because they are smaller than the 31-member operational system.
- The feature pipeline no longer invents `member_count=31` when provenance is missing.

The repository already contains 20 registered Indian monitoring locations; this patch does not duplicate or overwrite that registry.


## Accuracy rule

The NOAA GEFSv12 reforecast archive does **not** contain a +0h forecast field in the retrieved Days:1-10 forecast message. This patch therefore starts at +3h and never fabricates a +0h forecast. All requested leads must be exact 3-hour leads.
