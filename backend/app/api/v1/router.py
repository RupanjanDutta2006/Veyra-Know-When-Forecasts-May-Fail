"""V1 API Router combining all v1 endpoints."""
from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    certification,
    dashboard,
    disagreement,
    evaluation,
    health,
    metrics,
    multi_location,
    predict,
    revision,
    spatial,
)

api_router = APIRouter()

api_router.include_router(
    health.router,
    tags=["Health"],
)

api_router.include_router(
    metrics.router,
    tags=["Observability"],
)

api_router.include_router(
    predict.router,
    tags=["Prediction"],
)

api_router.include_router(
    multi_location.router,
    tags=["Multi-Location"],
)

api_router.include_router(
    evaluation.router,
    tags=["Model Evaluation"],
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard Intelligence"],
)

api_router.include_router(
    spatial.router,
    prefix="/spatial",
    tags=["Spatial Intelligence"],
)

api_router.include_router(
    disagreement.router,
    prefix="/disagreement",
    tags=["Forecast Disagreement Intelligence"],
)

api_router.include_router(
    revision.router,
    prefix="/revision",
    tags=["Forecast Revision Intelligence"],
)

api_router.include_router(
    certification.router,
    tags=["Scientific Certification"],
)
