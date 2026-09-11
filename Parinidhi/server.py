"""
Forecast-Bust Sentinel — Authoritative V2 HTTP Web Server.

Provides zero-dependency REST HTTP endpoints for Builder 1 integration
and serves the static dashboard.

Endpoints:
- GET  /api/health
- GET  /api/locations
- POST /api/forecast-risk
- POST /api/v1/predict
- GET  / (serves static/index.html)

Usage:
    python server.py          (starts on http://localhost:8001)
"""

import os
import sys
import json
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# Setup ecCodes library path if on Windows
_ENV_DIR = Path(__file__).resolve().parent / "scratch" / "env_eccodes"
_BIN_DIR = _ENV_DIR / "Library" / "bin"
if _BIN_DIR.exists():
    if str(_BIN_DIR) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(str(_BIN_DIR))
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.routes import ForecastBustAPI

# Singleton API instance
_api = None


def get_api() -> ForecastBustAPI:
    global _api
    if _api is None:
        _api = ForecastBustAPI()
    return _api


class VeyraHTTPRequestHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP Request Handler for Veyra Scientific Engine."""

    def _send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, User-Agent")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, User-Agent")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            try:
                health = get_api().get_health()
                self._send_json(health, 200)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
        elif path == "/api/locations":
            try:
                locs = get_api().list_locations()
                self._send_json(locs, 200)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
        elif path == "/api/scenarios":
            try:
                scenarios = get_api().list_scenarios()
                self._send_json(scenarios, 200)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
        elif path.startswith("/api/scenarios/"):
            try:
                parts = [p for p in path.split("/") if p and p != "api" and p != "scenarios"]
                scenario_id = parts[-1] if parts else "scenario_a_high_trust"
                result = get_api().run_scenario(scenario_id)
                self._send_json(result, 200)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
        elif path == "/" or path == "/index.html":
            static_file = PROJECT_ROOT / "static" / "index.html"
            if static_file.exists():
                content = static_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "Dashboard static file not found"}, 404)
        else:
            self._send_json({"error": f"Endpoint not found: {path}"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path in ("/api/forecast-risk", "/api/v1/predict"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_length)
                body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}

                forecast_data = (
                    body.get("forecast_data")
                    or body.get("records")
                    or body.get("forecasts")
                    or body
                )
                if isinstance(forecast_data, dict) and any(k in forecast_data for k in ("records", "forecast_data", "forecasts")):
                    forecast_data = forecast_data.get("records") or forecast_data.get("forecast_data") or forecast_data.get("forecasts")
                location_id = body.get("location_id", "delhi") if isinstance(body, dict) else "delhi"
                forecast_source = body.get("forecast_source", "NOAA_GEFS") if isinstance(body, dict) else "NOAA_GEFS"
                grid_resolution = body.get("grid_resolution") if isinstance(body, dict) else None

                result = get_api().get_forecast_risk(
                    forecast_input=forecast_data,
                    location_id=location_id,
                    forecast_source=forecast_source,
                    grid_resolution=grid_resolution,
                )
                self._send_json(result, 200)
            except Exception as exc:
                traceback.print_exc()
                self._send_json({"error": str(exc)}, 500)
        elif path == "/api/scenarios/run" or path == "/api/scenarios":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_length)
                body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                scenario_id = body.get("scenario_id", "scenario_a_high_trust")
                result = get_api().run_scenario(scenario_id)
                self._send_json(result, 200)
            except Exception as exc:
                traceback.print_exc()
                self._send_json({"error": str(exc)}, 500)
        else:
            self._send_json({"error": f"Endpoint not found: {path}"}, 404)

    def log_message(self, format, *args):
        # Suppress noisy standard request logs during tests
        pass


def run_server(port: int = 8001, host: str = "127.0.0.1"):
    print(f"Starting Veyra Authoritative V2 HTTP Server on http://{host}:{port} ...", flush=True)
    # Pre-warm model
    get_api()
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, VeyraHTTPRequestHandler)
    print(f"Veyra V2 HTTP Server ready and serving on http://{host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "127.0.0.1")
    run_server(port=port, host=host)
