"""Pytest fixtures and configuration."""
import pytest
from fastapi.testclient import TestClient
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """FastAPI TestClient session fixture."""
    return TestClient(app)


@pytest.fixture
def default_agent() -> ForecastBustAgent:
    """Default ForecastBustAgent fixture."""
    return ForecastBustAgent()


@pytest.fixture(autouse=True)
def reset_state_between_tests():
    """Reset rate limiter, forecast cache, and deduplicator between test cases for test isolation."""
    from backend.app.core.cache import forecast_cache, forecast_deduplicator
    from backend.app.core.rate_limiter import default_rate_limiter

    default_rate_limiter.reset()
    forecast_cache.clear()
    forecast_deduplicator.reset()
    yield
    default_rate_limiter.reset()
    forecast_cache.clear()
    forecast_deduplicator.reset()
