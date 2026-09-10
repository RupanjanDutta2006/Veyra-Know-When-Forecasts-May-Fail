"""Authoritative Builder 2 V3 Model Inference Adapter for Veyra.

Integrates Builder 2's frozen authoritative V3 Challenger model
(models/v3/lightgbm_v3_challenger.joblib) and its Isotonic Probability Calibrator
(models/v3/probability_calibrator_v3.joblib) into Builder 1's BaseModelService interface.

Strict Operating Contracts:
1. No Retraining / No Modification of frozen binaries.
2. SHA-256 integrity verification upon initialization.
3. Strict 50-feature schema matching models/v3/feature_names.json.
4. Correct unit-space transformation (Kelvin, Pascal, m/s).
5. Safe abstention on any artifact missing, hash mismatch, or schema error (NO silent fallback to legacy prototype).
6. Authoritative model identity: "veyra-v3-benchmark-lightgbm", operational threshold = 0.060.
"""

import hashlib
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from backend.app.builder2.v3_feature_pipeline import (
    V3_FEATURE_NAMES,
    V3FeaturePipeline,
    classify_v3_failure_fingerprint,
)
from backend.app.schemas.prediction import ReasonCode
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.base import (
    BaseModelService,
    FeatureResult,
    ModelResult,
    WeatherResult,
)

logger = logging.getLogger(__name__)

# Authoritative frozen artifact checksums
EXPECTED_MODEL_SHA256 = "00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660"
# Prompt included an extra '0' in one line ("...0e0ecbf..."), tolerate both 64-char canonical and prompt typo string
ACCEPTED_MODEL_SHAS = {
    EXPECTED_MODEL_SHA256,
    "00a8410746f4a0e0ecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660",
}
EXPECTED_CALIBRATOR_SHA256 = "9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531"

DEFAULT_V3_MODEL_DIR = Path("models/v3")
V3_MODEL_VERSION = "veyra-v3-benchmark-lightgbm"
V3_OPERATIONAL_THRESHOLD = 0.060


def calculate_sha256(file_path: Union[str, Path]) -> str:
    """Compute SHA-256 hex digest of a local file."""
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Artifact file not found: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Builder2V3ModelAdapter(BaseModelService):
    """Production Model Adapter for Authoritative V3 Challenger Model."""

    def __init__(
        self,
        model_dir: Optional[Union[str, Path]] = None,
        enforce_sha: bool = True,
        threshold: float = V3_OPERATIONAL_THRESHOLD,
    ):
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_V3_MODEL_DIR
        self.enforce_sha = enforce_sha
        self.threshold = threshold
        self.model_version: str = V3_MODEL_VERSION
        self.is_ready: bool = False
        self.init_error: Optional[str] = None

        self.booster: Optional[lgb.Booster] = None
        self.calibrator: Optional[Any] = None
        self.feature_names: List[str] = list(V3_FEATURE_NAMES)
        self.pipeline = V3FeaturePipeline()

        self.model_sha256: Optional[str] = None
        self.calibrator_sha256: Optional[str] = None

        self._initialize_artifacts()

    def _initialize_artifacts(self) -> None:
        """Locate, verify SHA-256, and deserialize authoritative V3 model and calibrator."""
        target_dir = self.model_dir
        if not target_dir.exists():
            # Check relative to project root or workspace
            alt_path = Path.cwd() / target_dir
            if alt_path.exists():
                target_dir = alt_path
            else:
                self.init_error = f"V3 model directory not found: {self.model_dir}"
                self.is_ready = False
                logger.warning(self.init_error)
                return

        model_path = target_dir / "lightgbm_v3_challenger.joblib"
        calibrator_path = target_dir / "probability_calibrator_v3.joblib"
        features_path = target_dir / "feature_names.json"

        # 1. Existence check
        for path, name in [
            (model_path, "Model"),
            (calibrator_path, "Calibrator"),
            (features_path, "Feature Schema"),
        ]:
            if not path.exists():
                self.init_error = f"Authoritative V3 {name} artifact missing at '{path}'"
                self.is_ready = False
                logger.error(self.init_error)
                return

        # 2. SHA-256 verification
        try:
            self.model_sha256 = calculate_sha256(model_path)
            self.calibrator_sha256 = calculate_sha256(calibrator_path)

            if self.enforce_sha:
                if self.model_sha256 not in ACCEPTED_MODEL_SHAS:
                    self.init_error = (
                        f"Model SHA-256 mismatch! Got: {self.model_sha256}, "
                        f"expected: {EXPECTED_MODEL_SHA256}"
                    )
                    self.is_ready = False
                    logger.critical(self.init_error)
                    return

                if self.calibrator_sha256 != EXPECTED_CALIBRATOR_SHA256:
                    self.init_error = (
                        f"Calibrator SHA-256 mismatch! Got: {self.calibrator_sha256}, "
                        f"expected: {EXPECTED_CALIBRATOR_SHA256}"
                    )
                    self.is_ready = False
                    logger.critical(self.init_error)
                    return
        except Exception as exc:
            self.init_error = f"Failed to compute SHA-256 for V3 artifacts: {exc}"
            self.is_ready = False
            logger.error(self.init_error)
            return

        # 3. Schema verification
        try:
            loaded_features = json.loads(features_path.read_text(encoding="utf-8"))
            if len(loaded_features) != 50:
                self.init_error = f"Expected 50 features in {features_path}, found {len(loaded_features)}"
                self.is_ready = False
                logger.error(self.init_error)
                return
            self.feature_names = loaded_features
        except Exception as exc:
            self.init_error = f"Failed to load V3 feature schema: {exc}"
            self.is_ready = False
            logger.error(self.init_error)
            return

        # 4. Deserialization & Booster Verification
        try:
            raw_model = joblib.load(model_path)
            if hasattr(raw_model, "booster_"):
                self.booster = raw_model.booster_
            elif isinstance(raw_model, lgb.Booster):
                self.booster = raw_model
            else:
                self.booster = getattr(raw_model, "_Booster", raw_model)

            booster_features = self.booster.feature_name()
            if booster_features != self.feature_names:
                self.init_error = (
                    "Booster feature order does not match authoritative feature_names.json!"
                )
                self.is_ready = False
                logger.error(self.init_error)
                return

            self.calibrator = joblib.load(calibrator_path)
            self.is_ready = True
            logger.info(
                "Authoritative V3 Model Adapter loaded successfully. Model SHA: %s..., Calibrator SHA: %s...",
                self.model_sha256[:12],
                self.calibrator_sha256[:12],
            )
        except Exception as exc:
            self.init_error = f"Failed to deserialize V3 artifacts: {exc}"
            self.is_ready = False
            logger.error(self.init_error)

    def validate_features(self, df_features: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """Verify the feature matrix strictly satisfies the 50-feature contract."""
        if df_features.empty:
            return False, "Feature DataFrame is empty"

        if len(df_features.columns) != 50:
            return False, f"Expected exactly 50 features, got {len(df_features.columns)}"

        missing = [c for c in self.feature_names if c not in df_features.columns]
        if missing:
            return False, f"Missing required V3 features: {missing}"

        # Check finiteness
        for col in self.feature_names:
            vals = df_features[col]
            if vals.isna().any():
                return False, f"Feature '{col}' contains NaN values"
            if np.isinf(vals).any():
                return False, f"Feature '{col}' contains infinite values"

        return True, None

    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Execute calibrated forecast-bust prediction conforming to BaseModelService."""
        # 1. Check adapter readiness
        if not self.is_ready or self.booster is None or self.calibrator is None:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={
                    "status": ReasonCode.MODEL_NOT_READY.value,
                    "error_detail": self.init_error or "V3 model not ready",
                },
                error=self.init_error or "Authoritative V3 model artifacts are unavailable or failed integrity check",
            )

        # 2. Check input readiness
        if not feature_result.is_ready or feature_result.error:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error=feature_result.error or "Features not ready for V3 model inference",
            )

        # 3. Construct DataFrame with exact 50 ordered features
        if feature_result.features and len(feature_result.features) >= 50:
            df_features = pd.DataFrame([feature_result.features])
        elif feature_result.metadata.get("feature_matrix_rows"):
            df_features = pd.DataFrame(feature_result.metadata["feature_matrix_rows"])
        elif feature_result.features:
            df_features = pd.DataFrame([feature_result.features])
        else:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error="FeatureResult contains no feature dictionary or matrix rows",
            )

        # Reorder columns strictly to canonical V3 order
        try:
            df_features = df_features[self.feature_names].copy()
        except KeyError as ke:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.QC_FAILED.value},
                error=f"Input features missing required V3 feature: {ke}",
            )

        # 4. Validate feature matrix
        is_valid, val_err = self.validate_features(df_features)
        if not is_valid:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.QC_FAILED.value, "validation_error": val_err},
                error=val_err,
            )

        # 5. Execute LightGBM inference + TreeSHAP explainability
        try:
            # Predict raw probability
            raw_prob_arr = self.booster.predict(df_features)
            raw_prob = float(raw_prob_arr[0])

            # Predict calibrated probability using authoritative Isotonic Calibrator
            try:
                if self.calibrator is None:
                    raise ValueError("Calibrator artifact is not loaded")
                cal_prob_arr = self.calibrator.predict(np.array([raw_prob]))
                val_cal = float(cal_prob_arr[0])
                if math.isnan(val_cal) or math.isinf(val_cal):
                    raise ValueError(f"Calibrator produced non-finite output: {val_cal}")
                cal_prob = float(np.clip(val_cal, 0.0, 1.0))
                calibration_status = "CALIBRATED"
            except Exception as cal_err:
                logger.error("V3 probability calibration failed: %s", cal_err)
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={
                        "status": ReasonCode.CALIBRATION_FAILURE.value,
                        "calibration_status": "FAILED",
                        "raw_probability": float(raw_prob),
                        "historical_f1_threshold": self.threshold,
                        "threshold": self.threshold,
                        "calibration_error": str(cal_err),
                    },
                    error=f"Probability calibration failure: {cal_err}",
                )

            # TreeSHAP feature contributions
            contribs = self.booster.predict(df_features, pred_contrib=True)[0]
            feature_contribs = dict(zip(self.feature_names, contribs[:50]))
            sorted_contribs = sorted(feature_contribs.items(), key=lambda x: abs(x[1]), reverse=True)
            dominant_drivers = [feat for feat, val in sorted_contribs[:4] if abs(val) > 0.001]
            if not dominant_drivers:
                dominant_drivers = [sorted_contribs[0][0]]

            # Failure fingerprint archetype classification
            first_row_dict = df_features.iloc[0].to_dict()
            fingerprint_archetype = classify_v3_failure_fingerprint(first_row_dict)

            # Metadata enrichment
            metadata: Dict[str, Any] = {
                "status": "SUCCESS",
                "calibration_status": calibration_status,
                "model_name": "V3_Benchmark_Challenger",
                "model_version": self.model_version,
                "features_count": 50,
                "raw_probability": float(raw_prob),
                "calibrated_probability": float(cal_prob),
                "historical_f1_threshold": self.threshold,
                "threshold": self.threshold,
                "ood_score": float(first_row_dict.get("ood_score", 0.0)),
                "failure_fingerprint": {
                    "primary_archetype": fingerprint_archetype,
                    "structural_overconfidence": bool(first_row_dict.get("structural_overconfidence_risk", 0.0) > 20.0),
                    "dominant_drivers": dominant_drivers,
                    "description": f"Classified into V3 archetype '{fingerprint_archetype}'",
                },
                "dominant_risk_drivers": dominant_drivers,
                "shap_contributions": feature_contribs,
                "model_sha256": self.model_sha256,
                "calibrator_sha256": self.calibrator_sha256,
            }

            return ModelResult(
                probability=cal_prob,
                model_version=self.model_version,
                is_ready=True,
                metadata=metadata,
                error=None,
            )

        except Exception as exc:
            logger.error("V3 model inference threw unexpected exception: %s", exc)
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                error=f"V3 Model inference failed: {exc}",
            )
