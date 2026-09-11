"""Real NOAA GEFSv12 reforecast smoke test. Requires scratch/env_eccodes."""
from ingestion.historical_gefs_collector import HistoricalGEFSCollector


df, manifest = HistoricalGEFSCollector().collect_run(
    "2017-03-14T00:00:00Z", 22.5726, 88.3639, "kolkata",
    horizon_hours=12, step_hours=3, variables=("temperature_2m",),
)
print(df[["issue_time","valid_time","lead_hours","value","unit","ensemble_mean","ensemble_std","member_count","member_ids","grid_latitude","grid_longitude","spatial_distance_km"]].to_string(index=False))
print("SOURCE:", manifest["source"])
print("MODEL:", manifest["model"])
print("MEMBERS:", manifest["member_codes"])
print("GRID:", manifest["grid_latitude"], manifest["grid_longitude"])
