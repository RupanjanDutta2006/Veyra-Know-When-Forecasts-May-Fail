# Veyra — Developer Command Guide & Cheat Sheet

This cheat sheet summarizes all common development, testing, and operational commands for **Veyra — Know When Forecasts May Fail**.

---

## 🛠️ Environment Setup

```bash
# Clone the repository
git clone https://github.com/RupanjanDutta2006/Veyra-Know-When-Forecasts-May-Fail.git
cd "Veyra — Know When Forecasts May Fail"

# Install all dependencies
python -m pip install -r requirements.txt
```

---

## 🚀 Running the Backend Server

```bash
# Start FastAPI backend with hot reloading
python -m uvicorn backend.app.main:app --reload --port 8000
```

### Access Local Endpoints:
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check:** `curl http://127.0.0.1:8000/v1/health`
- **Predict Bust Risk:**
  ```bash
  curl -X POST http://127.0.0.1:8000/v1/predict \
       -H "Content-Type: application/json" \
       -d '{"location": "London"}'
  ```

---

## 🧪 Automated Testing (Pytest)

```bash
# Run full automated test suite (92 tests)
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test modules
python -m pytest backend/tests/test_live_serving.py -v
python -m pytest backend/tests/test_final_readiness.py -v
python -m pytest backend/tests/test_ml_model_and_eval.py -v
```

---

## 🔍 Specialized Subsystem Smoke Tests

```bash
# 1. Weather Ingestion Smoke Test (Day 3)
python scripts/smoke_test_weather.py

# 2. Historical Verification & Bust Labeling Smoke Test (Day 4)
python scripts/smoke_test_historical.py

# 3. Feature Engineering & ML Pipeline Smoke Test (Day 5)
python scripts/smoke_test_ml.py

# 4. Live Model Serving Smoke Test (Day 6)
python scripts/smoke_test_serving.py

# 5. Final End-to-End System Readiness Smoke Test (Day 7)
python scripts/smoke_test_final.py
```

---

## 🌿 Git Operations & Status

```bash
# Check working tree status
git status

# View recent commit history
git log --oneline -10

# Check active branch and tracking
git branch -vv
```
