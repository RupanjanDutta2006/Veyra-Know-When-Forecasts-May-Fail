"""Model Persistence and Artifact Management for Veyra ML Pipelines."""
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import joblib

from backend.app.ml.baseline_model import LogisticRegressionBustModel
from backend.app.ml.evaluation import EvaluationReport
from backend.app.ml.features import FeaturePipeline


@dataclass
class ModelMetadata:
    """Comprehensive serializable metadata tracking model provenance and performance."""

    model_type: str = "LogisticRegression"
    model_version: str = "baseline-logistic-v1.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    feature_schema_version: str = "veyra-features-v1.0"
    feature_names: list[str] = field(default_factory=list)
    split_strategy: str = "TemporalChronoSplit_70_15_15"
    threshold_policy: str = "QuantileBustPolicy_q95"
    train_samples: int = 0
    val_samples: int = 0
    test_samples: int = 0
    train_time_range: tuple[str, str] = ("", "")
    val_time_range: tuple[str, str] = ("", "")
    test_time_range: tuple[str, str] = ("", "")
    val_metrics: Optional[dict[str, Any]] = None
    test_metrics: Optional[dict[str, Any]] = None
    coefficients: dict[str, float] = field(default_factory=dict)
    is_live_ready: bool = False  # Maintained as False until offline verification is complete


class ModelArtifactManager:
    """Handles serialization and loading of trained models, feature pipelines, and metadata."""

    def __init__(self, artifacts_dir: str = "models"):
        self.artifacts_dir = artifacts_dir

    def save_artifact(
        self,
        model: LogisticRegressionBustModel,
        pipeline: FeaturePipeline,
        metadata: ModelMetadata,
        artifact_name: str = "baseline_logistic_v1",
    ) -> tuple[str, str]:
        """Save model bundle (joblib) and human-readable metadata (JSON)."""
        os.makedirs(self.artifacts_dir, exist_ok=True)
        bundle_path = os.path.join(self.artifacts_dir, f"{artifact_name}.joblib")
        meta_path = os.path.join(self.artifacts_dir, f"{artifact_name}_metadata.json")

        # Save binary bundle
        bundle = {
            "model": model,
            "pipeline": pipeline,
            "metadata": asdict(metadata),
        }
        joblib.dump(bundle, bundle_path)

        # Save metadata JSON
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(asdict(metadata), f, indent=2)

        return bundle_path, meta_path

    def load_artifact(self, artifact_name: str = "baseline_logistic_v1") -> tuple[LogisticRegressionBustModel, FeaturePipeline, dict[str, Any]]:
        """Load model bundle and feature pipeline."""
        bundle_path = os.path.join(self.artifacts_dir, f"{artifact_name}.joblib")
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"Model artifact not found: {bundle_path}")

        bundle = joblib.load(bundle_path)
        return bundle["model"], bundle["pipeline"], bundle["metadata"]
