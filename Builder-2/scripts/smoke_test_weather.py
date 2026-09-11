import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


def run_smoke_test(location: str = "London") -> bool:
    print("=" * 60)
    print(f" VEYRA WEATHER INGESTION SMOKE TEST — Location: {location}")
    print("=" * 60)

    service = OpenMeteoGEFSWeatherService(timeout_seconds=10)
    print(f"[1/3] Resolving coordinates and querying live forecast feed...")

    try:
        result = service.get_forecast(location)
    except Exception as exc:
        print(f"[-] Network query failed: {exc}")
        return False

    print(f"[2/3] Response received from provider: {result.data_version}")
    print(f"      - Available: {result.is_available}")
    print(f"      - QC Passed: {result.quality_flags.get('qc_passed', False)}")

    if not result.is_available:
        print(f"[-] Ingestion or QC Error: {result.error}")
        print(f"    Violations: {result.metadata.get('violations', [])}")
        return False

    raw_dataset = result.raw_data
    records = raw_dataset.get("records", [])
    print(f"[3/3] Parsed {len(records)} Canonical Forecast Records successfully.")

    if records:
        print("\n--- SAMPLE CANONICAL RECORDS (First 3 Time-Steps) ---")
        for i, rec in enumerate(records[:3]):
            print(
                f"  Record #{i+1}: Var={rec['variable']:<20} | Val={rec['value']} {rec['unit']:<8} "
                f"| Issue={rec['issue_time']} | Valid={rec['valid_time']} | Lead={rec['lead_hours']}h"
            )
        print("-----------------------------------------------------")

    print("\n[+] SMOKE TEST COMPLETED SUCCESSFULLY: Real data reaches backend and passes QC.")
    return True


if __name__ == "__main__":
    success = run_smoke_test("London")
    sys.exit(0 if success else 1)
