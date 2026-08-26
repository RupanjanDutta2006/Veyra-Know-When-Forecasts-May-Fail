"""Application Settings and Configuration."""
import os
from pydantic import BaseModel


class Settings(BaseModel):
    """Global configuration settings for Forecast-Bust Sentinel."""

    PROJECT_NAME: str = "Forecast-Bust Sentinel API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/v1"
    SERVICE_NAME: str = "forecast-bust-sentinel"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

    # Future Model Settings (Builder 2 hooks)
    DEFAULT_MODEL_VERSION: str | None = None
    DEFAULT_DATA_VERSION: str | None = None

    # Builder 2 Runtime Model Artifact Directory
    BUILDER2_MODEL_DIR: str | None = os.getenv("BUILDER2_MODEL_DIR", None)


settings = Settings()
