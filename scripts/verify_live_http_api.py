"""Live HTTP Verification Script for Veyra REST API."""
import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def make_request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as err:
        body = json.loads(err.read().decode("utf-8"))
        return err.code, body
    except Exception as exc:
        return 0, {"error": str(exc)}

def main():
    print("=" * 70)
    print(" VEYRA REAL HTTP API END-TO-END VERIFICATION")
    print(f" Target: {BASE_URL}")
    print("=" * 70)

    # 1. Health Check
    print("\n[1/10] Testing GET /v1/health...")
    status, body = make_request("GET", "/v1/health")
    print(f"  Status: {status} | Body: {body}")
    assert status == 200, f"Expected 200, got {status}"
    assert body.get("status") in ("ok", "healthy")
    assert body.get("service") == "forecast-bust-sentinel"
    print("  [+] GET /v1/health: PASS")

    # 2. OpenAPI Documentation Generation
    print("\n[2/10] Testing GET /openapi.json...")
    status, body = make_request("GET", "/openapi.json")
    assert status == 200, f"Expected 200, got {status}"
    assert body.get("info", {}).get("title") == "Forecast-Bust Sentinel API"
    assert "/v1/predict" in body.get("paths", {})
    print(f"  [+] GET /openapi.json: PASS (Title: '{body['info']['title']}', Version: '{body['info']['version']}')")

    # 3. Valid Kolkata Prediction
    print("\n[3/10] Testing POST /v1/predict for 'Kolkata'...")
    kolkata_payload = {
        "location": "Kolkata",
        "variable": "temperature_2m",
        "issue_time": "2026-08-27T00:00:00Z",
        "valid_time": "2026-08-28T00:00:00Z",
    }
    status, body = make_request("POST", "/v1/predict", kolkata_payload)
    print(f"  Status: {status}")
    print(f"  Location:         {body.get('location')}")
    print(f"  Bust Probability: {body.get('bust_probability')}")
    print(f"  Risk Level:       {body.get('risk_level')}")
    print(f"  Trust State:      {body.get('trust_state')}")
    print(f"  Abstain:          {body.get('abstain')}")
    print(f"  Reason Codes:     {body.get('reason_codes')}")
    print(f"  Model Version:    {body.get('model_version')}")
    print(f"  Data Version:     {body.get('data_version')}")
    assert status == 200, f"Expected 200, got {status}"
    assert body.get("location") == "Kolkata"
    assert body.get("abstain") is False
    assert body.get("bust_probability") is not None
    assert 0.0 <= body.get("bust_probability") <= 1.0
    assert body.get("model_version") == "prototype-gbm-v1"
    assert body.get("data_version") == "gefs-openmeteo-v1.0"
    print("  [+] Valid Kolkata Prediction: PASS")

    # 4. Valid London Prediction
    print("\n[4/10] Testing POST /v1/predict for 'London'...")
    london_payload = {"location": "London"}
    status, body = make_request("POST", "/v1/predict", london_payload)
    print(f"  Status: {status} | P(bust): {body.get('bust_probability')} | Abstain: {body.get('abstain')}")
    assert status == 200, f"Expected 200, got {status}"
    assert body.get("location") == "London"
    assert body.get("abstain") is False
    assert body.get("bust_probability") is not None
    assert 0.0 <= body.get("bust_probability") <= 1.0
    print("  [+] Valid London Prediction: PASS")

    # 5. Invalid Location 'Atlantis' (Safe Abstention)
    print("\n[5/10] Testing POST /v1/predict for 'Atlantis' (Safe Abstention)...")
    atlantis_payload = {"location": "Atlantis"}
    status, body = make_request("POST", "/v1/predict", atlantis_payload)
    print(f"  Status: {status} | P(bust): {body.get('bust_probability')} | Abstain: {body.get('abstain')} | Reason: {body.get('reason_codes')}")
    assert status == 200, f"Expected 200, got {status}"
    assert body.get("location") == "Atlantis"
    assert body.get("abstain") is True
    assert body.get("bust_probability") is None
    assert body.get("trust_state") == "UNAVAILABLE"
    assert "INVALID_LOCATION" in body.get("reason_codes", [])
    print("  [+] Atlantis Safe Abstention: PASS")

    # 6. Negative Lead Time (Rejection)
    print("\n[6/10] Testing POST /v1/predict with Negative Lead Time (valid_time < issue_time)...")
    neg_lead_payload = {
        "location": "Kolkata",
        "issue_time": "2026-08-28T00:00:00Z",
        "valid_time": "2026-08-27T00:00:00Z",
    }
    status, body = make_request("POST", "/v1/predict", neg_lead_payload)
    print(f"  Status: {status} | Response: {body}")
    assert status == 422, f"Expected 422, got {status}"
    assert "strictly after issue_time" in str(body) or "Negative or zero" in str(body)
    print("  [+] Negative Lead Time Rejection: PASS (HTTP 422)")

    # 7. Zero Lead Time (Rejection)
    print("\n[7/10] Testing POST /v1/predict with Zero Lead Time (valid_time == issue_time)...")
    zero_lead_payload = {
        "location": "Kolkata",
        "issue_time": "2026-08-27T00:00:00Z",
        "valid_time": "2026-08-27T00:00:00Z",
    }
    status, body = make_request("POST", "/v1/predict", zero_lead_payload)
    print(f"  Status: {status} | Response: {body}")
    assert status == 422, f"Expected 422, got {status}"
    assert "strictly after issue_time" in str(body) or "Negative or zero" in str(body)
    print("  [+] Zero Lead Time Rejection: PASS (HTTP 422)")

    # 8. Excessive Lead Time (Rejection)
    print("\n[8/10] Testing POST /v1/predict with Horizon > 384h (576h)...")
    excessive_lead_payload = {
        "location": "Kolkata",
        "issue_time": "2026-08-27T00:00:00Z",
        "valid_time": "2026-09-20T00:00:00Z",
    }
    status, body = make_request("POST", "/v1/predict", excessive_lead_payload)
    print(f"  Status: {status} | Response: {body}")
    assert status == 422, f"Expected 422, got {status}"
    assert "exceeds the maximum supported forecast horizon" in str(body)
    print("  [+] Excessive Lead Time Rejection: PASS (HTTP 422)")

    # 9. Unsupported Variable (Rejection)
    print("\n[9/10] Testing POST /v1/predict with Unsupported Variable...")
    unsupported_var_payload = {
        "location": "Kolkata",
        "variable": "unsupported_stock_price",
    }
    status, body = make_request("POST", "/v1/predict", unsupported_var_payload)
    print(f"  Status: {status} | Response: {body}")
    assert status == 422, f"Expected 422, got {status}"
    assert "Unsupported forecast variable" in str(body)
    print("  [+] Unsupported Variable Rejection: PASS (HTTP 422)")

    # 10. Malformed Timestamp (Rejection)
    print("\n[10/10] Testing POST /v1/predict with Malformed Timestamp...")
    malformed_ts_payload = {
        "location": "Kolkata",
        "issue_time": "not-a-valid-date",
        "valid_time": "2026-08-28T00:00:00Z",
    }
    status, body = make_request("POST", "/v1/predict", malformed_ts_payload)
    print(f"  Status: {status} | Response: {body}")
    assert status == 422, f"Expected 422, got {status}"
    print("  [+] Malformed Timestamp Rejection: PASS (HTTP 422)")

    print("\n" + "=" * 70)
    print(" [+] ALL 10 REAL HTTP API TESTS PASSED SUCCESSFULLY")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
