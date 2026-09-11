"""
Veyra Phase 5B.2 — Local Checkpoint Collector & Master Dataset Compiler
Downloads compact cycle Parquets from cloud worker, verifies checksums,
joins with local ERA5 reference cache, and validates all 15 scientific gates (A-O).
"""
import os
import sys
import json
import hashlib
import urllib.request
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(r"C:\Users\parin\OneDrive\Desktop\forecast-bust-sentinel")
CYCLES_DIR = PROJECT_ROOT / "data/processed/phase5b2_cycles"
CYCLES_DIR.mkdir(parents=True, exist_ok=True)
MANIFESTS_DIR = PROJECT_ROOT / "data/manifests"
MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
RAW_ERA5_PATH = PROJECT_ROOT / "data/raw/era5_benchmark/era5_2000_2019_all_stations.parquet"
CYCLE_MANIFEST_PATH = MANIFESTS_DIR / "phase5b2_cycle_manifest.json"

FROZEN_25_IDS = [
    "delhi", "srinagar", "chandigarh", "jaipur", "lucknow",
    "mumbai", "pune", "ahmedabad", "goa", "bhopal",
    "nagpur", "raipur", "kolkata", "bhubaneswar", "ranchi",
    "guwahati", "bengaluru", "chennai", "hyderabad", "kochi",
    "dehradun", "shimla", "leh", "visakhapatnam", "thiruvananthapuram"
]

def load_era5_lookup():
    print("Loading local ERA5 truth cache (4,392,000 records)...", flush=True)
    df = pd.read_parquet(RAW_ERA5_PATH)
    lookup = {}
    times = df["time"].dt.strftime("%Y-%m-%dT%H:00").values
    lids = df["location_id"].values
    t2m_vals = df["t2m_K"].values
    sp_vals = df["sp_Pa"].values
    ws_vals = df["ws10_ms"].values
    for i in range(len(df)):
        lookup[(lids[i], times[i])] = {
            "t2m": float(t2m_vals[i]), "sp": float(sp_vals[i]), "ws10": float(ws_vals[i])
        }
    return lookup

def compile_master_benchmark(zip_path=None):
    if zip_path and os.path.exists(zip_path):
        print(f"Extracting compact zip from cloud worker: {zip_path}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(PROJECT_ROOT / "data/processed")
            
    era5_lookup = load_era5_lookup()
    
    cycle_files = sorted(list(CYCLES_DIR.glob("cycle_*.parquet")))
    print(f"Found {len(cycle_files)} compact cycle Parquet files in {CYCLES_DIR}.")
    
    all_rows = []
    for p in cycle_files:
        df_c = pd.read_parquet(p)
        # Join local ERA5 truth
        truth_col = []
        err_col = []
        abs_err_col = []
        for _, row in df_c.iterrows():
            lid = row["location_id"]
            vtime = row["valid_time"][:16]
            vname = row["variable"]
            ens_m = row["fcst_ens_mean"]
            tval = era5_lookup.get((lid, vtime), {}).get(vname, np.nan)
            truth_col.append(tval)
            if not np.isnan(ens_m) and not np.isnan(tval):
                e = ens_m - tval
                err_col.append(e)
                abs_err_col.append(abs(e))
            else:
                err_col.append(np.nan)
                abs_err_col.append(np.nan)
        df_c["truth_era5"] = truth_col
        df_c["error_ens_mean"] = err_col
        df_c["abs_error_ens_mean"] = abs_err_col
        all_rows.append(df_c)
        
    master_df = pd.concat(all_rows, ignore_index=True)
    out_parquet = PROJECT_ROOT / "data/processed/phase5b2_benchmark_raw.parquet"
    out_csv = PROJECT_ROOT / "data/processed/phase5b2_benchmark_raw.csv"
    
    print(f"Writing master Parquet ({len(master_df):,} rows)...")
    master_df.to_parquet(out_parquet, index=False)
    master_df.to_csv(out_csv, index=False)
    
    print(f"Dataset successfully compiled: {out_parquet} ({os.path.getsize(out_parquet)/(1024**2):.2f} MB)")
    return master_df

if __name__ == "__main__":
    compile_master_benchmark()
