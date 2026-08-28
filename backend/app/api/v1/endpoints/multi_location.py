"""Multi-location batch endpoints for forecast bust prediction and historical collection."""
from fastapi import APIRouter, Depends
from backend.app.schemas.multi_location import (
    MultiLocationHistoricalRequest,
    MultiLocationHistoricalResult,
    MultiLocationPredictionRequest,
    MultiLocationPredictionResult,
)
from backend.app.services.multi_location_service import (
    BaseMultiLocationService,
    MultiLocationService,
)

router = APIRouter()

# Default singleton multi-location service instance
_default_multi_location_service = MultiLocationService()


def get_multi_location_service() -> BaseMultiLocationService:
    """Dependency provider for MultiLocationService."""
    return _default_multi_location_service


@router.post(
    "/predict/batch",
    response_model=MultiLocationPredictionResult,
    summary="Batch Predict Forecast Bust Risk",
    description=(
        "Evaluates forecast bust risk across multiple locations simultaneously with "
        "per-location failure isolation, deduplication, and deterministic result ordering."
    ),
)
async def predict_batch_forecast_bust(
    request: MultiLocationPredictionRequest,
    service: BaseMultiLocationService = Depends(get_multi_location_service),
) -> MultiLocationPredictionResult:
    """Execute forecast bust prediction across multiple locations."""
    return service.predict_batch(request)


@router.post(
    "/historical/batch",
    response_model=MultiLocationHistoricalResult,
    summary="Batch Collect Historical Meteorological Data",
    description=(
        "Collects and normalizes historical weather and reanalysis data across multiple locations "
        "with per-location quality control, deduplication, and deterministic failure isolation."
    ),
)
async def collect_batch_historical_data(
    request: MultiLocationHistoricalRequest,
    service: BaseMultiLocationService = Depends(get_multi_location_service),
) -> MultiLocationHistoricalResult:
    """Collect historical meteorological data across multiple locations."""
    return service.collect_historical(request)
