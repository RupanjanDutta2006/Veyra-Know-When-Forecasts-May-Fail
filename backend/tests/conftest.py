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
def reset_rate_limiter_between_tests():
    """Reset rate limiter state between test cases for deterministic test isolation."""
    from backend.app.core.rate_limiter import default_rate_limiter

    default_rate_limiter.reset()
    yield
    default_rate_limiter.reset()
