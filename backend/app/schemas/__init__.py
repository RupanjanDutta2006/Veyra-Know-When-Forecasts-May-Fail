"""Schemas package exporting API and Data contracts."""
from backend.app.schemas.health import HealthResponse
from backend.app.schemas.historical import (
    CanonicalHistoricalRecord,
    HistoricalCollectionResult,
    HistoricalDataRequest,
)
from backend.app.schemas.location import ResolvedLocation
from backend.app.schemas.multi_location import (
    MAX_MULTI_LOCATION_BATCH_SIZE,
    MultiLocationHistoricalItemResult,
    MultiLocationHistoricalRequest,
    MultiLocationHistoricalResult,
    MultiLocationPredictionItemResult,
    MultiLocationPredictionRequest,
    MultiLocationPredictionResult,
)
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.schemas.reference import (
    ReferenceWeatherDataset,
    ReferenceWeatherRecord,
)
from backend.app.schemas.weather import (
    CanonicalForecastDataset,
    CanonicalForecastRecord,
)

__all__ = [
    "HealthResponse",
    "PredictionRequest",
    "PredictionResponse",
    "TrustState",
    "RiskLevel",
    "ReasonCode",
    "CanonicalForecastRecord",
    "CanonicalForecastDataset",
    "ReferenceWeatherRecord",
    "ReferenceWeatherDataset",
    "ResolvedLocation",
    "HistoricalDataRequest",
    "CanonicalHistoricalRecord",
    "HistoricalCollectionResult",
    "MAX_MULTI_LOCATION_BATCH_SIZE",
    "MultiLocationHistoricalRequest",
    "MultiLocationHistoricalItemResult",
    "MultiLocationHistoricalResult",
    "MultiLocationPredictionRequest",
    "MultiLocationPredictionItemResult",
    "MultiLocationPredictionResult",
]
