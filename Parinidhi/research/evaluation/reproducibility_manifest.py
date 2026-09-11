"""
Veyra — Reproducibility Manifest Generator (SIH26079)
Records full cryptographic provenance, software versions, feature schemas,
registry hashes, split configurations, and random seeds for scientific replication.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("veyra.reproducibility_manifest")


@dataclass
class ReproducibilityManifest:
    """Authoritative reproducibility manifest for the 1,040-cycle benchmark."""
    benchmark_id: str
    created_at_utc: str
    dataset_metadata: Dict[str, Any]
    code_provenance: Dict[str, Any]
    model_metadata: Dict[str, Any]
    feature_schema_metadata: Dict[str, Any]
    location_registry_metadata: Dict[str, Any]
    split_configuration: Dict[str, Any]
    threshold_configuration: Dict[str, Any]
    environment_dependencies: Dict[str, Any]
    random_seeds: Dict[str, int]
    evaluation_configuration: Dict[str, Any]
    status: str = "PENDING_DATASET"  # VALIDATED or PENDING_DATASET

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, filepath: str | Path) -> None:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info(f"Reproducibility manifest saved to {p}")


class ManifestBuilder:
    """Assembles the complete cryptographic reproducibility manifest."""

    @staticmethod
    def compute_file_sha256(filepath: str | Path) -> Optional[str]:
        """Computes SHA-256 hash of a file if it exists."""
        p = Path(filepath)
        if not p.exists() or not p.is_file():
            return None
        sha = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def get_git_commit_sha() -> str:
        """Retrieves git commit SHA if git repository is present."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return "UNTRACKED_OR_NO_GIT"

    @staticmethod
    def collect_dependencies() -> Dict[str, str]:
        """Collects installed versions of critical scientific dependencies."""
        deps = {}
        pkgs = ["numpy", "pandas", "scipy", "sklearn", "lightgbm", "joblib", "pyarrow", "eccodes"]
        for pkg in pkgs:
            try:
                mod = __import__(pkg)
                deps[pkg] = getattr(mod, "__version__", "INSTALLED_NO_VERSION")
            except Exception as e:
                deps[pkg] = f"UNAVAILABLE ({type(e).__name__})"
        return deps

    @classmethod
    def generate_manifest(
        cls,
        dataset_path: Optional[str | Path] = None,
        benchmark_id: str = "veyra_phase5b2_1040cycle_benchmark",
        is_real_dataset: bool = False
    ) -> ReproducibilityManifest:
        """Builds the complete manifest."""
        now_utc = datetime.now(timezone.utc).isoformat()
        git_sha = cls.get_git_commit_sha()
        deps = cls.collect_dependencies()

        # Hashes of canonical components
        registry_path = Path(__file__).resolve().parent.parent.parent / "pipeline" / "canonical_locations.py"
        registry_hash = cls.compute_file_sha256(registry_path) if registry_path.exists() else "MISSING"

        champion_model_path = Path(__file__).resolve().parent.parent.parent / "models" / "v2" / "lightgbm_v2_champion.joblib"
        model_hash = cls.compute_file_sha256(champion_model_path) if champion_model_path.exists() else "MISSING"

        dataset_hash = None
        if dataset_path and Path(dataset_path).exists():
            dataset_hash = cls.compute_file_sha256(dataset_path)

        dataset_meta = {
            "name": "NOAA_GEFSv12_Reforecast_2000_2019_Canonical25",
            "cycle_count": 1040,
            "station_count": 25,
            "variable_count": 3,
            "lead_count": 10,
            "expected_row_count": 780000,
            "leads_hours": [24, 48, 72, 96, 120, 144, 168, 192, 216, 240],
            "variables": ["temperature_2m", "surface_pressure", "wind_speed_10m"],
            "verification_reference": "ERA5_Reanalysis (reanalysis verification/reference; not station ground truth)",
            "dataset_sha256": dataset_hash or "PENDING_DOWNLOAD_FROM_COLAB_DRIVE",
            "extraction_status": "COMPLETED_ON_COLAB" if is_real_dataset else "RUNNING_IN_COLAB"
        }

        code_prov = {
            "git_commit_sha": git_sha,
            "repo_name": "Veyra / Forecast-Bust Sentinel (SIH26079)",
            "os_platform": platform.platform(),
            "python_runtime": sys.version
        }

        model_meta = {
            "production_champion": "Frozen V2 (LightGBM)",
            "champion_model_file": "models/v2/lightgbm_v2_champion.joblib",
            "champion_sha256": model_hash,
            "calibrator_version": "v2_isotonic_lead_conditioned",
            "challengers_evaluated": ["E4_Quantile_Mesh", "E5_Parametric_Gaussian_GPD"]
        }

        feature_meta = {
            "feature_pipeline_version": "v2_physics_aware_26feat",
            "schema_contract_version": "2026.1",
            "feature_count": 26,
            "core_groups": ["ensemble_moments", "temporal_trends", "spatial_topographic", "error_signals"]
        }

        loc_meta = {
            "registry_version": "25_canonical_indian_synoptic",
            "registry_file_sha256": registry_hash,
            "station_count": 25,
            "regions": ["NW", "NC", "NE", "WZ", "SZ"]
        }

        split_cfg = {
            "strategy": "chronological_weekly_buffered",
            "train_cycles": 730,
            "train_date_range": "2000-01-01 to 2013-12-31 (approx 70%)",
            "val_cycles": 155,
            "val_date_range": "2014-01-01 to 2016-12-31 (approx 15%)",
            "test_cycles": 155,
            "test_date_range": "2017-01-01 to 2019-12-31 (approx 15%)",
            "temporal_buffer_weeks": 2
        }

        threshold_cfg = {
            "bust_definition": {
                "temperature_2m_threshold": 3.0,
                "surface_pressure_threshold": 4.0,
                "wind_speed_10m_threshold": 3.5,
                "lead_slack_multiplier": "1.0 + 0.05 * (lead_hours / 24.0)"
            },
            "trust_horizon_p_crit": {
                "value": 0.35,
                "scientific_status": "DESIGN_CHOICE",
                "documentation": "Configurable research/product design threshold. Subject to empirical post-dataset validation."
            },
            "failure_fingerprints_mahalanobis_threshold": {
                "value": 40.0,
                "scientific_status": "DESIGN_CHOICE",
                "documentation": "Non-causal diagnostic pattern threshold for archetype association."
            }
        }

        random_seeds = {
            "numpy_seed": 42,
            "lightgbm_seed": 42,
            "bootstrap_seed": 2026,
            "cv_split_seed": 42
        }

        eval_cfg = {
            "lead_eval_mode": "individual_disaggregated (+24 to +240)",
            "calibration_modes": ["uncalibrated", "global_isotonic", "lead_conditioned_isotonic"],
            "bootstrap_iterations": 1000,
            "bootstrap_group_column": "cycle_idx",
            "bootstrap_ci_level": 0.95,
            "spatial_evaluation": "leave_region_out_5fold",
            "temporal_evaluation": "walk_forward_expanding_window"
        }

        return ReproducibilityManifest(
            benchmark_id=benchmark_id,
            created_at_utc=now_utc,
            dataset_metadata=dataset_meta,
            code_provenance=code_prov,
            model_metadata=model_meta,
            feature_schema_metadata=feature_meta,
            location_registry_metadata=loc_meta,
            split_configuration=split_cfg,
            threshold_configuration=threshold_cfg,
            environment_dependencies=deps,
            random_seeds=random_seeds,
            evaluation_configuration=eval_cfg,
            status="VALIDATED" if is_real_dataset else "PENDING_DATASET"
        )
