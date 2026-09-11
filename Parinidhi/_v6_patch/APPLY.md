# Data Foundation v6

Apply this patch from the repository root. It fixes Herbie/pandas timezone incompatibility in `ingestion/historical_gefs_collector.py`: canonical issue times remain UTC-aware, but Herbie receives a UTC-normalized timezone-naive datetime.

Files: `ingestion/historical_gefs_collector.py`.
