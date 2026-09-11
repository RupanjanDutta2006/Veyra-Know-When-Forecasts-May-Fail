"""
Veyra Phase 5B.2 — AWS In-Region Cloud Worker Extractor
Executes in AWS us-east-1 directly adjacent to s3://noaa-gefs-retrospective.
Downloads byte ranges internally, decodes with ecCodes in RAM, extracts station values,
writes atomic compact Parquet checkpoints, and auto-shuts down.
"""
import os
import sys
import json
import math
import time
import datetime
import hashlib
import urllib.request
import concurrent.futures
from pathlib import Path
import numpy as np
import pandas as pd
import requests

BASE_S3_URL = "https://noaa-gefs-retrospective.s3.amazonaws.com"
WORK_DIR = Path("/opt/veyra_extraction")
WORK_DIR.mkdir(parents=True, exist_ok=True)
CYCLES_DIR = WORK_DIR / "cycles"
CYCLES_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_DIR = WORK_DIR / "manifests"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
CYCLE_MANIFEST_PATH = MANIFEST_DIR / "phase5b2_cycle_manifest.json"

# Canonical 25 Locations
FROZEN_25_LOCATIONS = [
    {"location_id": "delhi", "name": "Delhi", "lat": 28.6139, "lon": 77.2090},
    {"location_id": "srinagar", "name": "Srinagar", "lat": 34.0837, "lon": 74.7973},
    {"location_id": "chandigarh", "name": "Chandigarh", "lat": 30.7333, "lon": 76.7794},
    {"location_id": "jaipur", "name": "Jaipur", "lat": 26.9124, "lon": 75.7873},
    {"location_id": "lucknow", "name": "Lucknow", "lat": 26.8467, "lon": 80.9462},
    {"location_id": "mumbai", "name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"location_id": "pune", "name": "Pune", "lat": 18.5204, "lon": 73.8567},
    {"location_id": "ahmedabad", "name": "Ahmedabad", "lat": 23.0225, "lon": 72.5714},
    {"location_id": "goa", "name": "Goa", "lat": 15.2993, "lon": 74.1240},
    {"location_id": "bhopal", "name": "Bhopal", "lat": 23.2599, "lon": 77.4126},
    {"location_id": "nagpur", "name": "Nagpur", "lat": 21.1458, "lon": 79.0882},
    {"location_id": "raipur", "name": "Raipur", "lat": 21.2514, "lon": 81.6296},
    {"location_id": "kolkata", "name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"location_id": "bhubaneswar", "name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
    {"location_id": "ranchi", "name": "Ranchi", "lat": 23.3441, "lon": 85.3096},
    {"location_id": "guwahati", "name": "Guwahati", "lat": 26.1445, "lon": 91.7362},
    {"location_id": "bengaluru", "name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"location_id": "chennai", "name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"location_id": "hyderabad", "name": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    {"location_id": "kochi", "name": "Kochi", "lat": 9.9312, "lon": 76.2673},
    {"location_id": "dehradun", "name": "Dehradun", "lat": 30.3165, "lon": 78.0322},
    {"location_id": "shimla", "name": "Shimla", "lat": 31.1048, "lon": 77.1734},
    {"location_id": "leh", "name": "Leh", "lat": 34.1526, "lon": 77.5771},
    {"location_id": "visakhapatnam", "name": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185},
    {"location_id": "thiruvananthapuram", "name": "Thiruvananthapuram", "lat": 8.5241, "lon": 76.9366}
]

MEMBERS = ["c00", "p01", "p02", "p03", "p04"]
TARGET_LEADS = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240]
VAR_PREFIXES = ["tmp_2m", "pres_sfc", "ugrd_hgt", "vgrd_hgt"]

PREV_LEAD_MAP = {
    24: 48, 48: 72, 72: 96, 96: 120, 120: 144,
    144: 168, 168: 192, 192: 216, 216: 240, 240: None
}

# Import ecCodes
try:
    import eccodes
except ImportError:
    print("FATAL: ecCodes Python binding not found. Please install eccodes.", file=sys.stderr)
    sys.exit(1)

# Precompute Bilinear Interpolation Weights
def build_station_weights(loc_list):
    meta = {}
    for loc in loc_list:
        lid = loc["location_id"]
        lat = loc["lat"]
        lon = loc["lon"]
        lat_idx_f = (90.0 - lat) / 0.25
        lon_idx_f = lon / 0.25
        j0 = int(math.floor(lat_idx_f))
        j1 = min(j0 + 1, 720)
        i0 = int(math.floor(lon_idx_f)) % 1440
        i1 = (i0 + 1) % 1440
        w_lat = lat_idx_f - j0
        w_lon = lon_idx_f - i0
        w00 = (1.0 - w_lat) * (1.0 - w_lon)
        w01 = (1.0 - w_lat) * w_lon
        w10 = w_lat * (1.0 - w_lon)
        w11 = w_lat * w_lon
        meta[lid] = {
            "indices": (j0 * 1440 + i0, j0 * 1440 + i1, j1 * 1440 + i0, j1 * 1440 + i1),
            "weights": (w00, w01, w10, w11),
            "lat": lat, "lon": lon, "name": loc.get("name", lid)
        }
    return meta

STATION_WEIGHTS = build_station_weights(FROZEN_25_LOCATIONS)

def extract_station_values(field_values: np.ndarray) -> dict:
    res = {}
    for lid, m in STATION_WEIGHTS.items():
        i00, i01, i10, i11 = m["indices"]
        w00, w01, w10, w11 = m["weights"]
        val = w00 * field_values[i00] + w01 * field_values[i01] + w10 * field_values[i10] + w11 * field_values[i11]
        res[lid] = float(val)
    return res

def get_cycle_list():
    anchor = datetime.datetime(2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    cycles = []
    # Train: 0..729 (730 cycles)
    for k in range(0, 730):
        t0 = anchor + datetime.timedelta(days=7 * k)
        cycles.append({"cycle_idx": k, "t0": t0, "cycle_date_str": t0.strftime("%Y%m%d%H"), "cycle_iso": t0.isoformat(), "partition": "train"})
    # Val: 731..885 (155 cycles)
    for k in range(731, 886):
        t0 = anchor + datetime.timedelta(days=7 * k)
        cycles.append({"cycle_idx": k, "t0": t0, "cycle_date_str": t0.strftime("%Y%m%d%H"), "cycle_iso": t0.isoformat(), "partition": "val"})
    # Test: 888..1042 (155 cycles)
    for k in range(888, 1043):
        t0 = anchor + datetime.timedelta(days=7 * k)
        cycles.append({"cycle_idx": k, "t0": t0, "cycle_date_str": t0.strftime("%Y%m%d%H"), "cycle_iso": t0.isoformat(), "partition": "test"})
    return cycles

SESSION = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=3)
SESSION.mount("https://", adapter)

IDX_CACHE = {}

def fetch_idx(year: str, cycle_str: str, member: str, var_prefix: str):
    cache_key = (year, cycle_str, member, var_prefix)
    if cache_key in IDX_CACHE:
        return IDX_CACHE[cache_key]
    url = f"{BASE_S3_URL}/GEFSv12/reforecast/{year}/{cycle_str}/{member}/Days%3A1-10/{var_prefix}_{cycle_str}_{member}.grib2.idx"
    for _ in range(3):
        try:
            resp = SESSION.get(url, headers={"User-Agent": "VeyraSentinel/5B.2-CloudWorker"}, timeout=15)
            if resp.status_code == 200:
                lines = [l for l in resp.text.strip().split("\n") if l]
                entries = []
                for line in lines:
                    parts = line.split(":")
                    entries.append({"msg_num": int(parts[0]), "offset": int(parts[1]), "var": parts[3], "level": parts[4], "step": parts[5]})
                IDX_CACHE[cache_key] = entries
                return entries
            elif resp.status_code == 404:
                IDX_CACHE[cache_key] = None
                return None
        except Exception:
            time.sleep(0.5)
    return None

def download_range(url: str, byte_start: int, byte_end):
    headers = {"User-Agent": "VeyraSentinel/5B.2-CloudWorker", "Range": f"bytes={byte_start}-{byte_end}" if byte_end is not None else f"bytes={byte_start}-"}
    for _ in range(3):
        try:
            resp = SESSION.get(url, headers=headers, timeout=20)
            if resp.status_code in [200, 206]:
                return resp.content
        except Exception:
            time.sleep(0.5)
    return None

def extract_cycle(cycle_info):
    cycle_idx = cycle_info["cycle_idx"]
    t0 = cycle_info["t0"]
    cycle_str = cycle_info["cycle_date_str"]
    year = cycle_str[:4]
    partition = cycle_info["partition"]
    
    t0_prev = t0 - datetime.timedelta(days=1)
    cycle_prev_str = t0_prev.strftime("%Y%m%d%H")
    year_prev = cycle_prev_str[:4]
    has_prev_cycle = (cycle_idx > 0)
    
    # 1. Fetch .idx files
    idx_requests = [(year, cycle_str, m, vp) for m in MEMBERS for vp in VAR_PREFIXES]
    if has_prev_cycle:
        idx_requests.extend([(year_prev, cycle_prev_str, m, vp) for m in MEMBERS for vp in VAR_PREFIXES])
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        f_map = {executor.submit(fetch_idx, y, c, m, vp): (y, c, m, vp) for y, c, m, vp in idx_requests}
        for f in concurrent.futures.as_completed(f_map):
            f.result()
            
    # 2. Build download plan
    current_plan = []
    for m in MEMBERS:
        for vp in VAR_PREFIXES:
            entries = IDX_CACHE.get((year, cycle_str, m, vp))
            if not entries: continue
            grib_url = f"{BASE_S3_URL}/GEFSv12/reforecast/{year}/{cycle_str}/{m}/Days%3A1-10/{vp}_{cycle_str}_{m}.grib2"
            for lead in TARGET_LEADS:
                step_str = f"{lead} hour fcst"
                matching = [e for e in entries if e["step"] == step_str]
                if not matching: continue
                m_entry = [e for e in matching if "10 m above ground" in e["level"]][0] if vp in ["ugrd_hgt", "vgrd_hgt"] else matching[0]
                msg_idx = m_entry["msg_num"] - 1
                b_start = m_entry["offset"]
                b_end = entries[msg_idx + 1]["offset"] - 1 if msg_idx + 1 < len(entries) else None
                current_plan.append({"type": "current", "member": m, "var_prefix": vp, "lead": lead, "url": grib_url, "b_start": b_start, "b_end": b_end})
                
    prev_plan = []
    if has_prev_cycle:
        for m in MEMBERS:
            for vp in VAR_PREFIXES:
                entries = IDX_CACHE.get((year_prev, cycle_prev_str, m, vp))
                if not entries: continue
                grib_url = f"{BASE_S3_URL}/GEFSv12/reforecast/{year_prev}/{cycle_prev_str}/{m}/Days%3A1-10/{vp}_{cycle_prev_str}_{m}.grib2"
                for target_lead, prev_lead in PREV_LEAD_MAP.items():
                    if prev_lead is None: continue
                    step_str = f"{prev_lead} hour fcst"
                    matching = [e for e in entries if e["step"] == step_str]
                    if not matching: continue
                    m_entry = [e for e in matching if "10 m above ground" in e["level"]][0] if vp in ["ugrd_hgt", "vgrd_hgt"] else matching[0]
                    msg_idx = m_entry["msg_num"] - 1
                    b_start = m_entry["offset"]
                    b_end = entries[msg_idx + 1]["offset"] - 1 if msg_idx + 1 < len(entries) else None
                    prev_plan.append({"type": "prev", "member": m, "var_prefix": vp, "target_lead": target_lead, "prev_lead": prev_lead, "url": grib_url, "b_start": b_start, "b_end": b_end})
                    
    # 3. Concurrent Range Download inside AWS internal network
    all_download_items = current_plan + prev_plan
    downloaded_raw = []
    total_cycle_bytes = 0
    
    def dl_worker(item):
        raw = download_range(item["url"], item["b_start"], item["b_end"])
        return item, raw
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        f_list = [executor.submit(dl_worker, item) for item in all_download_items]
        for f in concurrent.futures.as_completed(f_list):
            item, raw = f.result()
            if raw:
                downloaded_raw.append((item, raw))
                total_cycle_bytes += len(raw)
                
    # 4. In-Memory ecCodes Decoding & Spatial Sampling
    current_extracted = {}
    prev_extracted = {}
    for item, raw in downloaded_raw:
        try:
            gid = eccodes.codes_new_from_message(raw)
            vals = eccodes.codes_get_values(gid)
            eccodes.codes_release(gid)
            st_dict = extract_station_values(vals)
            if item["type"] == "current":
                current_extracted[(item["member"], item["var_prefix"], item["lead"])] = st_dict
            else:
                prev_extracted[(item["member"], item["var_prefix"], item["target_lead"])] = st_dict
        except Exception:
            pass
            
    # 5. Row Assembly (25 stations x 3 vars x 10 leads = 750 rows)
    rows = []
    for lid, station_meta in STATION_WEIGHTS.items():
        lat, lon, name = station_meta["lat"], station_meta["lon"], station_meta["name"]
        
        std_by_var_lead = {}
        for var_name in ["t2m", "sp", "ws10"]:
            for lead in TARGET_LEADS:
                m_vals = []
                for m in MEMBERS:
                    if var_name == "t2m": v = current_extracted.get((m, "tmp_2m", lead), {}).get(lid, np.nan)
                    elif var_name == "sp": v = current_extracted.get((m, "pres_sfc", lead), {}).get(lid, np.nan)
                    elif var_name == "ws10":
                        u = current_extracted.get((m, "ugrd_hgt", lead), {}).get(lid, np.nan)
                        vc = current_extracted.get((m, "vgrd_hgt", lead), {}).get(lid, np.nan)
                        v = math.sqrt(u**2 + vc**2) if (not np.isnan(u) and not np.isnan(vc)) else np.nan
                    m_vals.append(v)
                valid = [x for x in m_vals if not np.isnan(x)]
                std_by_var_lead[(var_name, lead)] = float(np.std(valid, ddof=1)) if len(valid) == 5 else np.nan
                
        for var_name in ["t2m", "sp", "ws10"]:
            for lead in TARGET_LEADS:
                valid_time = t0 + datetime.timedelta(hours=lead)
                m_vals = []
                for m in MEMBERS:
                    if var_name == "t2m": v = current_extracted.get((m, "tmp_2m", lead), {}).get(lid, np.nan)
                    elif var_name == "sp": v = current_extracted.get((m, "pres_sfc", lead), {}).get(lid, np.nan)
                    elif var_name == "ws10":
                        u = current_extracted.get((m, "ugrd_hgt", lead), {}).get(lid, np.nan)
                        vc = current_extracted.get((m, "vgrd_hgt", lead), {}).get(lid, np.nan)
                        v = math.sqrt(u**2 + vc**2) if (not np.isnan(u) and not np.isnan(vc)) else np.nan
                    m_vals.append(v)
                    
                valid_m = [x for x in m_vals if not np.isnan(x)]
                if len(valid_m) == 5:
                    ens_mean = float(np.mean(valid_m))
                    ens_std = float(np.std(valid_m, ddof=1))
                    ens_min = float(np.min(valid_m))
                    ens_max = float(np.max(valid_m))
                    ens_spread = float(ens_max - ens_min)
                else:
                    ens_mean = ens_std = ens_min = ens_max = ens_spread = np.nan
                    
                # Dispersion Growth Rate
                disp_growth = np.nan if lead == 24 else ((std_by_var_lead.get((var_name, lead), np.nan) - std_by_var_lead.get((var_name, lead - 24), np.nan)) / 24.0)
                
                # Previous Vintage
                if not has_prev_cycle or lead == 240:
                    prev_c00 = prev_p01 = prev_p02 = prev_p03 = prev_p04 = prev_mean = prev_std = vintage_drift = np.nan
                    prev_lead_h = None if lead == 240 else PREV_LEAD_MAP[lead]
                else:
                    prev_lead_h = PREV_LEAD_MAP[lead]
                    prev_m = []
                    for m in MEMBERS:
                        if var_name == "t2m": pv = prev_extracted.get((m, "tmp_2m", lead), {}).get(lid, np.nan)
                        elif var_name == "sp": pv = prev_extracted.get((m, "pres_sfc", lead), {}).get(lid, np.nan)
                        elif var_name == "ws10":
                            pu = prev_extracted.get((m, "ugrd_hgt", lead), {}).get(lid, np.nan)
                            pvc = prev_extracted.get((m, "vgrd_hgt", lead), {}).get(lid, np.nan)
                            pv = math.sqrt(pu**2 + pvc**2) if (not np.isnan(pu) and not np.isnan(pvc)) else np.nan
                        prev_m.append(pv)
                    prev_c00, prev_p01, prev_p02, prev_p03, prev_p04 = prev_m
                    valid_pv = [x for x in prev_m if not np.isnan(x)]
                    if len(valid_pv) == 5:
                        prev_mean = float(np.mean(valid_pv))
                        prev_std = float(np.std(valid_pv, ddof=1))
                        vintage_drift = float(ens_mean - prev_mean) if not np.isnan(ens_mean) else np.nan
                    else:
                        prev_mean = prev_std = vintage_drift = np.nan
                        
                rows.append({
                    "cycle_idx": cycle_idx,
                    "cycle_date": cycle_info["cycle_iso"],
                    "partition": partition,
                    "location_id": lid,
                    "station_name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "variable": var_name,
                    "lead_hours": lead,
                    "valid_time": valid_time.isoformat(),
                    "fcst_c00": m_vals[0], "fcst_p01": m_vals[1], "fcst_p02": m_vals[2], "fcst_p03": m_vals[3], "fcst_p04": m_vals[4],
                    "fcst_ens_mean": ens_mean, "fcst_ens_std": ens_std, "fcst_ens_min": ens_min, "fcst_ens_max": ens_max, "fcst_ens_spread": ens_spread,
                    "dispersion_growth_rate_24h": disp_growth,
                    "prev_cycle_date": t0_prev.isoformat() if has_prev_cycle else None,
                    "prev_lead_hours": prev_lead_h,
                    "prev_fcst_c00": prev_c00, "prev_fcst_p01": prev_p01, "prev_fcst_p02": prev_p02, "prev_fcst_p03": prev_p03, "prev_fcst_p04": prev_p04,
                    "prev_ens_mean": prev_mean, "prev_ens_std": prev_std,
                    "vintage_drift": vintage_drift,
                    "qc_flag": 0 if not np.isnan(ens_mean) else 1
                })
                
    return rows, total_cycle_bytes, len(downloaded_raw)

def main():
    pilot_mode = ("--pilot" in sys.argv)
    print("=" * 75)
    print(f"VEYRA PHASE 5B.2 — AWS IN-REGION CLOUD WORKER (Pilot Mode: {pilot_mode})")
    print("=" * 75)
    
    cycles = get_cycle_list()
    if pilot_mode:
        cycles = [c for c in cycles if c["cycle_idx"] == 1]  # Pilot: Cycle 0001 (2000-01-08 00Z)
        
    print(f"Executing {len(cycles)} cycles directly inside AWS us-east-1...")
    t0_start = time.time()
    
    cycle_manifest = {"completed_cycles": {}}
    for c_info in cycles:
        k = c_info["cycle_idx"]
        k_str = f"{k:04d}"
        cycle_file = CYCLES_DIR / f"cycle_{k_str}.parquet"
        
        t_c = time.time()
        c_rows, cycle_bytes, decoded_msgs = extract_cycle(c_info)
        
        df_cycle = pd.DataFrame(c_rows)
        temp_file = CYCLES_DIR / f"cycle_{k_str}.tmp.parquet"
        df_cycle.to_parquet(temp_file, index=False)
        temp_file.replace(cycle_file)
        
        c_elapsed = time.time() - t_c
        file_bytes = os.path.getsize(cycle_file)
        sha256 = hashlib.sha256(cycle_file.read_bytes()).hexdigest()
        
        cycle_manifest["completed_cycles"][k_str] = {
            "cycle_idx": k, "cycle_date": c_info["cycle_iso"], "partition": c_info["partition"],
            "rows": len(c_rows), "bytes_transferred": cycle_bytes, "decoded_msgs": decoded_msgs,
            "sha256": sha256, "parquet_size_bytes": file_bytes, "elapsed_seconds": round(c_elapsed, 2)
        }
        print(f"Cycle {k:04d}: {len(c_rows)} rows | NOAA: {cycle_bytes/(1024**2):.1f} MB | Output: {file_bytes/1024:.1f} KB in {c_elapsed:.2f}s", flush=True)
        
    with open(CYCLE_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(cycle_manifest, f, indent=2)
        
    print(f"\nAll requested cycles complete in {time.time() - t0_start:.2f}s!")
    print(f"Outputs saved to {CYCLES_DIR} with manifest at {CYCLE_MANIFEST_PATH}")
    
    # Auto-shutdown trigger if in production cloud mode
    if "--auto-shutdown" in sys.argv:
        print("Auto-shutdown enabled: Triggering system halt...")
        os.system("sudo shutdown -h now")

if __name__ == "__main__":
    main()
