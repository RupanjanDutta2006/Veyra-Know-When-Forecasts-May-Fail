"""V1 API Router combining all v1 endpoints."""
from fastapi import APIRouter
from backend.app.api.v1.endpoints import health, predict

api_router = APIRouter()

api_router.include_router(
    health.router,
    tags=["Health"],
)

api_router.include_router(
    predict.router,
    tags=["Prediction"],
)
