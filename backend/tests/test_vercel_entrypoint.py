"""Regression tests for Vercel deployment entrypoint and configuration contract."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.app.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client() -> TestClient:
    """Test client for entrypoint validation."""
    return TestClient(app)


def test_fastapi_entrypoint_instance():
    """Verify backend.app.main:app is an active FastAPI instance."""
    assert isinstance(app, FastAPI), "app must be an instance of FastAPI"
    assert app.title == "Forecast-Bust Sentinel API"


def test_fastapi_authoritative_routes_registered():
    """Verify all authoritative production routes are registered on the entrypoint."""
    top_paths = {getattr(r, "path", "") for r in app.routes}
    api_paths = set(app.openapi()["paths"].keys())

    # Required endpoints
    assert "/docs" in top_paths, "Swagger UI /docs route must be present"
    assert "/openapi.json" in top_paths, "OpenAPI JSON schema /openapi.json must be present"
    assert "/" in top_paths, "Root / route must be present"
    assert "/dashboard" in top_paths, "/dashboard route must be present"
    assert "/v1/health" in api_paths, "/v1/health route must be present"
    assert "/v1/predict" in api_paths, "/v1/predict route must be present"
    assert "/v1/dashboard/intelligence" in api_paths, "/v1/dashboard/intelligence route must be present"


def test_health_endpoint_response(client: TestClient):
    """Verify /v1/health returns 200 OK with service identity."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "forecast-bust-sentinel"
    assert "version" in payload


def test_root_endpoint_browser_vs_api(client: TestClient):
    """Verify GET / serves frontend HTML to browsers and JSON metadata to API clients."""
    # 1. API client request (JSON)
    json_resp = client.get("/", headers={"accept": "application/json"})
    assert json_resp.status_code == 200
    json_data = json_resp.json()
    assert "docs" in json_data
    assert "dashboard" in json_data
    assert "health" in json_data

    # 2. Browser request (HTML) when frontend/dist is built
    dist_index = REPO_ROOT / "frontend" / "dist" / "index.html"
    if dist_index.is_file():
        browser_resp = client.get(
            "/",
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        )
        assert browser_resp.status_code == 200
        assert "text/html" in browser_resp.headers.get("content-type", "")
        assert "<div id=\"root\">" in browser_resp.text


def test_spa_fallback_preserves_api_404(client: TestClient):
    """Verify SPA fallback does not intercept non-existent /v1 API routes."""
    response = client.get("/v1/nonexistent-endpoint")
    assert response.status_code == 404


def test_pyproject_toml_vercel_entrypoint():
    """Verify pyproject.toml defines [tool.vercel] entrypoint = 'backend.app.main:app'."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    assert pyproject_path.is_file(), "pyproject.toml must exist at repository root"
    content = pyproject_path.read_text(encoding="utf-8")
    assert "[tool.vercel]" in content, "[tool.vercel] table must be defined in pyproject.toml"
    assert 'entrypoint = "backend.app.main:app"' in content, "Vercel entrypoint must point to backend.app.main:app"


def test_vercel_json_build_command():
    """Verify vercel.json defines frontend buildCommand."""
    vercel_json_path = REPO_ROOT / "vercel.json"
    assert vercel_json_path.is_file(), "vercel.json must exist at repository root"
    data = json.loads(vercel_json_path.read_text(encoding="utf-8"))
    assert "buildCommand" in data
    assert "npm" in data["buildCommand"]
    assert "build" in data["buildCommand"]


def test_v3_artifacts_exact_provenance():
    """Verify V3 model artifacts SHA-256 and feature schema count."""
    model_path = REPO_ROOT / "models" / "v3" / "lightgbm_v3_challenger.joblib"
    calibrator_path = REPO_ROOT / "models" / "v3" / "probability_calibrator_v3.joblib"
    features_path = REPO_ROOT / "models" / "v3" / "feature_names.json"

    assert model_path.is_file(), "lightgbm_v3_challenger.joblib must exist"
    assert calibrator_path.is_file(), "probability_calibrator_v3.joblib must exist"
    assert features_path.is_file(), "feature_names.json must exist"

    def compute_sha(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest().lower()

    model_sha = compute_sha(model_path)
    calibrator_sha = compute_sha(calibrator_path)

    expected_model_sha = "00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660"
    expected_calibrator_sha = "9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531"

    assert model_sha == expected_model_sha, f"Model SHA mismatch: {model_sha} != {expected_model_sha}"
    assert calibrator_sha == expected_calibrator_sha, f"Calibrator SHA mismatch: {calibrator_sha} != {expected_calibrator_sha}"

    with open(features_path, "r", encoding="utf-8") as f:
        features = json.load(f)
    assert len(features) == 50, f"Expected 50 features, found {len(features)}"


def test_bundled_libgomp_runtime_presence_and_checksum():
    """Verify single authoritative bundled libgomp.so.1 exists with verified x86_64 ELF format and SHA-256."""
    expected_sha = "98b21ff32bb07b53f1fb266d887d2db0086ea66c8ad03696a1db53f65321cd94"

    loc = REPO_ROOT / "lib" / "libgomp.so.1"
    assert loc.is_file(), f"{loc} must exist as the authoritative bundled library file"
    data = loc.read_bytes()
    # Verify ELF header
    assert data[:4] == b"\x7fELF", f"{loc} must be an ELF binary"
    assert data[4] == 2, f"{loc} must be 64-bit"
    assert data[5] == 1, f"{loc} must be Little-Endian"
    actual_sha = hashlib.sha256(data).hexdigest()
    assert actual_sha == expected_sha, f"Checksum mismatch for {loc}: {actual_sha} != {expected_sha}"

    # Verify license notice exists alongside the binary
    assert (REPO_ROOT / "lib" / "LICENSE.txt").is_file()


def test_vercel_json_functions_include_files():
    """Verify vercel.json configures functions.includeFiles for lib directory."""
    vercel_json_path = REPO_ROOT / "vercel.json"
    assert vercel_json_path.is_file(), "vercel.json must exist at repository root"
    data = json.loads(vercel_json_path.read_text(encoding="utf-8"))
    assert "functions" in data, "functions section must be present in vercel.json"
    functions = data["functions"]
    # Check that either entrypoint or wildcard includes lib/**
    matched = False
    for pattern, cfg in functions.items():
        if "includeFiles" in cfg and "lib" in cfg["includeFiles"]:
            matched = True
            break
    assert matched, "vercel.json functions must include lib/** in includeFiles"


def test_runtime_compat_module_execution():
    """Verify runtime_compat.ensure_linux_runtimes runs cleanly without throwing exceptions."""
    from backend.app.core.runtime_compat import ensure_linux_runtimes
    assert ensure_linux_runtimes() is True

