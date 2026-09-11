"""
Worker script executed inside isolated ecCodes environment.
Fetches GRIB2 byte slices from NOAA S3 and decodes target grid points using ecCodes.
Uses multithreading for network I/O and a mutex lock for thread-safe ecCodes C-library calls.
"""

import concurrent.futures
import json
import math
import sys
import threading
import requests
import eccodes

BASE_S3_URL = "https://noaa-gefs-pds.s3.amazonaws.com"
decode_lock = threading.Lock()

# Thread-local storage for requests session
thread_local = threading.local()


def get_session():
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=3)
        s.mount("https://", adapter)
        s.headers.update({"User-Agent": "ForecastBustSentinel/1.0"})
        thread_local.session = s
    return thread_local.session


def fetch_and_decode_single(date_str, cycle, member, step, grid_flat_idx):
    """
    Fetch .idx file, resolve byte ranges for TMP, PRES, UGRD, VGRD, download slices, decode point.
    """
    base_file_url = f"{BASE_S3_URL}/gefs.{date_str}/{cycle}/atmos/pgrb2ap5/{member}.t{cycle}z.pgrb2a.0p50.{step}"
    idx_url = f"{base_file_url}.idx"
    session = get_session()

    try:
        resp = session.get(idx_url, timeout=25)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "date": date_str, "member": member, "step": step}
        idx_lines = resp.text.splitlines()
    except Exception as e:
        return {"error": str(e), "date": date_str, "member": member, "step": step}

    ranges = {}
    for i, line in enumerate(idx_lines):
        parts = line.split(":")
        if len(parts) >= 6:
            key = f"{parts[3]}:{parts[4]}"
            start_b = int(parts[1])
            end_b = int(idx_lines[i+1].split(":")[1]) - 1 if i + 1 < len(idx_lines) else ""
            if key == "TMP:2 m above ground":
                ranges["TMP"] = (start_b, end_b)
            elif key == "PRES:surface":
                ranges["PRES"] = (start_b, end_b)
            elif key == "UGRD:10 m above ground":
                ranges["UGRD"] = (start_b, end_b)
            elif key == "VGRD:10 m above ground":
                ranges["VGRD"] = (start_b, end_b)

    res = {"date": date_str, "member": member, "step": step}

    # 1. Download byte buffers concurrently
    buf_tmp = None
    if "TMP" in ranges:
        s, e = ranges["TMP"]
        try:
            r = session.get(base_file_url, headers={"Range": f"bytes={s}-{e}"}, timeout=25)
            if r.status_code in [200, 206]:
                buf_tmp = r.content
        except Exception:
            pass

    buf_pres = None
    if "PRES" in ranges:
        s, e = ranges["PRES"]
        try:
            r = session.get(base_file_url, headers={"Range": f"bytes={s}-{e}"}, timeout=25)
            if r.status_code in [200, 206]:
                buf_pres = r.content
        except Exception:
            pass

    buf_uv = None
    buf_u = None
    buf_v = None
    is_uv_contiguous = False
    if "UGRD" in ranges and "VGRD" in ranges:
        u_s, u_e = ranges["UGRD"]
        v_s, v_e = ranges["VGRD"]
        if u_e + 1 == v_s:
            is_uv_contiguous = True
            try:
                r = session.get(base_file_url, headers={"Range": f"bytes={u_s}-{v_e}"}, timeout=25)
                if r.status_code in [200, 206]:
                    buf_uv = r.content
            except Exception:
                pass
        else:
            try:
                r_u = session.get(base_file_url, headers={"Range": f"bytes={u_s}-{u_e}"}, timeout=25)
                if r_u.status_code in [200, 206]:
                    buf_u = r_u.content
            except Exception:
                pass
            try:
                r_v = session.get(base_file_url, headers={"Range": f"bytes={v_s}-{v_e}"}, timeout=25)
                if r_v.status_code in [200, 206]:
                    buf_v = r_v.content
            except Exception:
                pass

    # 2. Decode under mutex lock for thread-safe ecCodes C-library execution
    with decode_lock:
        if buf_tmp:
            try:
                gid = eccodes.codes_new_from_message(buf_tmp)
                vals = eccodes.codes_get_values(gid)
                res["temperature_2m"] = float(vals[grid_flat_idx]) - 273.15 # K to °C
                eccodes.codes_release(gid)
            except Exception:
                pass

        if buf_pres:
            try:
                gid = eccodes.codes_new_from_message(buf_pres)
                vals = eccodes.codes_get_values(gid)
                res["surface_pressure"] = float(vals[grid_flat_idx]) / 100.0 # Pa to hPa
                eccodes.codes_release(gid)
            except Exception:
                pass

        if is_uv_contiguous and buf_uv:
            try:
                gid_u = eccodes.codes_new_from_message(buf_uv)
                u_val = float(eccodes.codes_get_values(gid_u)[grid_flat_idx])
                offset = eccodes.codes_get(gid_u, "totalLength")
                eccodes.codes_release(gid_u)
                gid_v = eccodes.codes_new_from_message(buf_uv[offset:])
                v_val = float(eccodes.codes_get_values(gid_v)[grid_flat_idx])
                eccodes.codes_release(gid_v)
                res["wind_speed_10m"] = math.sqrt(u_val**2 + v_val**2) * 3.6 # m/s to km/h
            except Exception:
                pass
        elif buf_u and buf_v:
            try:
                gid_u = eccodes.codes_new_from_message(buf_u)
                u_val = float(eccodes.codes_get_values(gid_u)[grid_flat_idx])
                eccodes.codes_release(gid_u)
                gid_v = eccodes.codes_new_from_message(buf_v)
                v_val = float(eccodes.codes_get_values(gid_v)[grid_flat_idx])
                eccodes.codes_release(gid_v)
                res["wind_speed_10m"] = math.sqrt(u_val**2 + v_val**2) * 3.6 # m/s to km/h
            except Exception:
                pass

    return res


def main():
    if len(sys.argv) < 2:
        print("Usage: python s3_eccodes_worker.py <config_json_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    dates = config["dates"]
    cycle = config["cycle"]
    steps = config["steps"]
    members = config["members"]
    grid_flat_idx = config["grid_flat_idx"]
    max_workers = config.get("max_workers", 25)
    output_json = config["output_json"]

    total_tasks = len(dates) * len(steps) * len(members)
    print(f"[Worker] Launching {total_tasks} S3 extraction tasks with {max_workers} threads...")

    results_tree = {d: {s: {} for s in steps} for d in dates}

    completed_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_and_decode_single, d, cycle, m, s, grid_flat_idx): (d, s, m)
            for d in dates
            for s in steps
            for m in members
        }

        for f in concurrent.futures.as_completed(futures):
            d, s, m = futures[f]
            completed_count += 1
            if completed_count % 500 == 0 or completed_count == total_tasks:
                print(f"[Worker] Progress: {completed_count}/{total_tasks} ({completed_count*100.0/total_tasks:.1f}%)")
            try:
                res = f.result()
                if "error" not in res:
                    results_tree[d][s][m] = {
                        "temperature_2m": res.get("temperature_2m"),
                        "surface_pressure": res.get("surface_pressure"),
                        "wind_speed_10m": res.get("wind_speed_10m"),
                    }
            except Exception as err:
                print(f"[Worker Error] ({d}, {s}, {m}): {err}")

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results_tree, f, indent=2)

    print(f"[Worker] Successfully saved output to {output_json}")


if __name__ == "__main__":
    main()
