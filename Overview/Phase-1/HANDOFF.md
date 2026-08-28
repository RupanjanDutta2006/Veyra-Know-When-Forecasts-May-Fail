# Veyra — Builder 2 Integration & Handoff Specification

This specification outlines the clean architecture boundaries and typed contracts designed by **Builder 1** to enable **Builder 2** to seamlessly plug in advanced meteorological datasets, enriched atmospheric features, gradient-boosted decision trees, and calibrated probability models without rewriting backend orchestration.

---

## 1. Modular Architecture Overview

```text
PredictionRequest
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                     ForecastBustAgent                       │
│                                                             │
│  1. WeatherService ──► 2. QC ──► 3. FeatureService          │
│                                           │                 │
│                                           ▼                 │
│  PredictionResponse ◄── 5. SafetyService ◄── 4. ModelService│
└─────────────────────────────────────────────────────────────┘
```

All communication between stages is governed by typed dataclasses defined in `backend/app/services/base.py`.

---

## 2. Core Service Interfaces (Builder 2 Extension Hooks)

### A. `BaseWeatherService`
Located at `backend/app/services/base.py`:
```python
class BaseWeatherService(ABC):
    @abstractmethod
    def get_forecast(
        self, location: str, target_date: Optional[str] = None
    ) -> WeatherResult:
        """Fetch raw forecast and atmospheric data for a given location."""
        pass
```
- **Builder 2 Tasks:** Ingest ECMWF IFS, GFS ensemble spreads, or blended multi-model ensembles.
- **Return Type:** `WeatherResult(location=..., raw_data=..., is_available=True, quality_flags=...)`.

---

### B. `BaseFeatureService`
Located at `backend/app/services/base.py`:
```python
class BaseFeatureService(ABC):
    @abstractmethod
    def build_features(self, weather_result: WeatherResult) -> FeatureResult:
        """Transform raw forecast data into engineered feature vectors."""
        pass
```
- **Builder 2 Tasks:** Compute ensemble spread (variance across 31 members), CAPE indices, vertical wind shear, boundary layer moisture divergence, and terrain complexity.
- **Inference Invariant:** Must strictly enforce zero leakage of ground-truth reference values (`observed_value`, `forecast_error`, `bust_label`).
- **Return Type:** `FeatureResult(location=..., features=..., feature_names=..., is_ready=True)`.

---

### C. `BaseModelService`
Located at `backend/app/services/base.py`:
```python
class BaseModelService(ABC):
    @abstractmethod
    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Generate calibrated forecast-bust probability given engineered features."""
        pass
```
- **Builder 2 Tasks:**
  1. Train Gradient-Boosted Decision Trees (`LightGBM` / `XGBoost`).
  2. Implement probability calibration (Isotonic Regression or Platt Scaling).
  3. Validate $P(\text{bust}) \in [0.0, 1.0]$.
  4. Serialize trained bundles and metadata using `ModelArtifactManager`.
- **Return Type:** `ModelResult(probability=float, model_version="lgbm-calibrated-v1", is_ready=True)`.

---

### D. `BaseSafetyService`
Located at `backend/app/services/base.py`:
```python
class BaseSafetyService(ABC):
    @abstractmethod
    def evaluate(
        self,
        weather_result: WeatherResult,
        feature_result: FeatureResult,
        model_result: ModelResult,
        context: Optional[dict[str, Any]] = None,
    ) -> SafetyAssessment:
        """Perform safety evaluation and return a SafetyAssessment."""
        pass
```
- **Builder 2 Tasks:** Add Mahalanobis distance OOD detection or conformal prediction bounds to flag unfamiliar atmospheric regimes.

---

## 3. Data Schemas & Historical Dataset Representation

### `CanonicalForecastRecord` (`backend/app/schemas/weather.py`)
Standard schema for every forecast point:
```python
class CanonicalForecastRecord(BaseModel):
    location: str
    latitude: float
    longitude: float
    issue_time: str      # ISO-8601 UTC
    valid_time: str      # ISO-8601 UTC
    lead_hours: int      # valid_time - issue_time in hours
    variable: str        # temperature_2m, surface_pressure, wind_speed_10m, etc.
    unit: str            # celsius, hPa, m/s, %, mm
    value: float
    source: str          # e.g., NOAA_GEFS_OPENMETEO
    member_count: Optional[int] = None
    ensemble_mean: Optional[float] = None
    ensemble_std: Optional[float] = None
    ensemble_min: Optional[float] = None
    ensemble_max: Optional[float] = None
```

### `HistoricalTrainingRow` (`backend/app/data/dataset.py`)
Standard schema for offline ML dataset rows:
- Strictly contains: `location`, `latitude`, `longitude`, `issue_time`, `valid_time`, `lead_hours`, `variable`, `unit`, `forecast_value`, `reference_value`, `forecast_error`, `absolute_error`, `bust_threshold`, `bust_label`, `season`, `month`, `source`.

---

## 4. How to Plug In Builder 2's Calibrated ML Model

1. **Train Model & Save Artifact:**
   ```python
   from backend.app.ml.artifacts import ModelArtifactManager, ModelMetadata

   manager = ModelArtifactManager(artifacts_dir="models")
   manager.save_artifact(
       artifact_name="lgbm_calibrated_v1",
       model=trained_lgbm_model,
       pipeline=feature_pipeline,
       metadata=ModelMetadata(
           model_type="LightGBMClassifier",
           model_version="lgbm-calibrated-v1.0",
           feature_names=feature_pipeline.get_feature_names(),
           is_calibrated=True,
       ),
   )
   ```

2. **Implement Model Service & Inject:**
   ```python
   from backend.app.services.base import BaseModelService, FeatureResult, ModelResult

   class CalibratedLGBMService(BaseModelService):
       def __init__(self):
           # Load artifact
           ...
       def predict(self, feature_result: FeatureResult) -> ModelResult:
           prob = self.calibrated_model.predict_proba(X)[0, 1]
           return ModelResult(probability=prob, model_version="lgbm-calibrated-v1.0", is_ready=True)
   ```

3. **Register Service in API (`backend/app/api/v1/endpoints/predict.py`):**
   ```python
   _default_agent = ForecastBustAgent(
       weather_service=OpenMeteoGEFSWeatherService(),
       feature_service=LiveFeatureService(),
       model_service=CalibratedLGBMService(),
       safety_evaluator=SafetyEvaluator(),
   )
   ```
   **Zero core pipeline changes required!**
