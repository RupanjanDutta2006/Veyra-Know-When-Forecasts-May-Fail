"""Application Settings and Configuration with centralized production hardening parameters."""
import os
from pathlib import Path
from pydantic import BaseModel, Field

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

    # Provider Timeouts (seconds)
    GEOCODING_TIMEOUT_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("GEOCODING_TIMEOUT_SECONDS", "10"))
    )
    WEATHER_TIMEOUT_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("WEATHER_TIMEOUT_SECONDS", "25"))
    )
    HISTORICAL_TIMEOUT_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("HISTORICAL_TIMEOUT_SECONDS", "15"))
    )
    REFERENCE_TIMEOUT_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("REFERENCE_TIMEOUT_SECONDS", "10"))
    )

    # Bounded HTTP Retries & Backoff
    MAX_HTTP_RETRIES: int = Field(
        default_factory=lambda: int(os.getenv("MAX_HTTP_RETRIES", "2"))
    )
    RETRY_BACKOFF_FACTOR: float = Field(
        default_factory=lambda: float(os.getenv("RETRY_BACKOFF_FACTOR", "0.3"))
    )

    # In-memory Caching (Location / Geocoding)
    CACHE_ENABLED: bool = Field(
        default_factory=lambda: os.getenv("CACHE_ENABLED", "True").lower() in ("true", "1", "yes")
    )
    CACHE_MAX_SIZE: int = Field(
        default_factory=lambda: int(os.getenv("CACHE_MAX_SIZE", "1024"))
    )
    CACHE_TTL_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    )

    # In-memory Short-Lived Weather Forecast Caching & Deduplication (Day 17)
    WEATHER_CACHE_ENABLED: bool = Field(
        default_factory=lambda: os.getenv("WEATHER_CACHE_ENABLED", "True").lower() in ("true", "1", "yes")
    )
    WEATHER_CACHE_MAX_SIZE: int = Field(
        default_factory=lambda: int(os.getenv("WEATHER_CACHE_MAX_SIZE", "512"))
    )
    WEATHER_CACHE_TTL_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "120"))
    )
    WEATHER_DEDUP_ENABLED: bool = Field(
        default_factory=lambda: os.getenv("WEATHER_DEDUP_ENABLED", "True").lower() in ("true", "1", "yes")
    )

    # In-process Rate Limiting / Abuse Protection
    RATE_LIMIT_ENABLED: bool = Field(
        default_factory=lambda: os.getenv("RATE_LIMIT_ENABLED", "True").lower() in ("true", "1", "yes")
    )
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "120"))
    )
    RATE_LIMIT_BURST_SIZE: int = Field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_BURST_SIZE", "30"))
    )

    # Observability & Logging
    LOG_LEVEL: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    LOG_FORMAT: str = Field(
        default_factory=lambda: os.getenv("LOG_FORMAT", "text")
    )
    STRUCTURED_LOGGING: bool = Field(
        default_factory=lambda: os.getenv("STRUCTURED_LOGGING", "True").lower() in ("true", "1", "yes")
    )
    METRICS_ENABLED: bool = Field(
        default_factory=lambda: os.getenv("METRICS_ENABLED", "True").lower() in ("true", "1", "yes")
    )
    ENABLE_SECURITY_HEADERS: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_SECURITY_HEADERS", "True").lower() in ("true", "1", "yes")
    )
    ENABLE_REQUEST_CORRELATION: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_REQUEST_CORRELATION", "True").lower() in ("true", "1", "yes")
    )

    # Multi-location Batch limits
    MAX_MULTI_LOCATION_BATCH_SIZE: int = Field(
        default_factory=lambda: int(os.getenv("MAX_MULTI_LOCATION_BATCH_SIZE", "50"))
    )

    # Server & Deployment Configuration
    HOST: str = Field(
        default_factory=lambda: os.getenv("HOST", "0.0.0.0")
    )
    PORT: int = Field(
        default_factory=lambda: int(os.getenv("PORT", "8000"))
    )

    # CORS Configuration (Production Security)
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
            ).split(",")
            if origin.strip()
        ]
    )
    CORS_ALLOW_ALL: bool = Field(
        default_factory=lambda: os.getenv("CORS_ALLOW_ALL", "False").lower() in ("true", "1", "yes")
    )


settings = Settings()
