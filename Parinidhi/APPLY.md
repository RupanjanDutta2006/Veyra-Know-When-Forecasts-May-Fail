# Data Foundation v8

This patch replaces the broken Herbie `xarray()` subset path with an explicit
`H.download(search=...)` followed by `cfgrib` opening of the returned local
file. The scientific source remains NOAA GEFSv12 reforecast; Builder 1 is not
changed.

Apply from the repository root:

```powershell
Expand-Archive -Path ".\\forecast-bust-sentinel-data-foundation-v8.zip" -DestinationPath ".\\_v8_patch" -Force
Copy-Item .\\_v8_patch\\* . -Recurse -Force
```

Then test the exact real NOAA run:

```powershell
conda run -p .\\scratch\\env_eccodes python -c "from ingestion.historical_gefs_collector import HistoricalGEFSCollector; df,m=HistoricalGEFSCollector().collect_run('2017-03-14T00:00:00Z',22.5726,88.3639,'kolkata',horizon_hours=12,step_hours=3); print(df[['issue_time','valid_time','lead_hours','variable','value','ensemble_mean','ensemble_std','member_count','member_ids','grid_latitude','grid_longitude','spatial_distance_km']].to_string(index=False)); print('MEMBERS:',m['member_codes']); print('ROWS:',len(df))"
```

The patch uses the official NOAA GEFSv12 reforecast data and keeps the existing
canonical output contract. It does not modify Builder 1.
