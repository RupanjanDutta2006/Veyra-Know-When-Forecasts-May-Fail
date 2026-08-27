"""Application Settings and Configuration."""
import os
from pathlib import Path
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DAY4_DIR = _REPO_ROOT / "models" / "day4"


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
    BUILDER2_MODEL_DIR: str | None = os.getenv(
        "BUILDER2_MODEL_DIR",
        str(_DEFAULT_DAY4_DIR) if _DEFAULT_DAY4_DIR.exists() else ("models/day4" if os.path.exists("models/day4") else None),
    )


settings = Settings()

