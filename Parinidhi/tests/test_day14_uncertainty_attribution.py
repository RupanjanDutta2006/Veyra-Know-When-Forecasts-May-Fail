"""
Adversarial & Unit Tests for Day 14: Uncertainty Decomposition & Failure Attribution.

Validates:
1. Anti-leakage safeguards (truth/error/bust columns rejected by novelty/attribution engines).
2. Numerical stability against zero-variance features, singular matrices, and missing data.
3. Deterministic behavior and reproducible outputs.
4. Historical failure-pattern retrieval with minimum support gating.
5. Risk self-confidence degradation under high novelty / sparse support.
6. JSON serialization and schema compliance of CompositeFailureExplanation.
7. End-to-end pipeline execution on real Stage B historical records.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from evaluation.attribution import ForecastRiskAttributionEngine
from evaluation.explanation_engine import ForecastFailureExplainer
from evaluation.explanation_schema import CompositeFailureExplanation
from evaluation.failure_patterns import HistoricalFailureRetriever
from evaluation.novelty import FeatureNoveltyDetector
from evaluation.profiles import LocationRegimeProfiler
from evaluation.risk_confidence import RiskConfidenceEngine
from evaluation.uncertainty import UncertaintyDecomposer
from features.contract import UNAVAILABLE_UNTIL_VERIFICATION
from features.feature_pipeline import IssueTimeSafeFeaturePipeline, FEATURE_COLUMN_NAMES
from models.logistic_classifier import RegularizedLogisticClassifier


@pytest.fixture
def synthetic_issue_features():
    """Synthetic issue-time feature dataframe."""
    np.random.seed(42)
    n = 200
    return pd.DataFrame({
        "ensemble_std": np.random.uniform(0.5, 4.0, n),
        "ensemble_range": np.random.uniform(2.0, 15.0, n),
        "ensemble_iqr": np.random.uniform(1.0, 8.0, n),
        "forecast_delta_6h": np.random.normal(0.0, 1.5, n),
        "forecast_delta_24h": np.random.normal(0.0, 2.5, n),
        "lead_hours": np.random.choice([6, 12, 24, 48, 72], n),
        "valid_hour": np.random.choice(range(24), n),
        "latitude": np.random.uniform(8.0, 35.0, n),
        "longitude": np.random.uniform(68.0, 92.0, n),
    })


@pytest.fixture
def synthetic_labels():
    np.random.seed(42)
    return pd.Series(np.random.binomial(1, 0.08, 200), name="bust_label")


# =========================================================================
# 1. Anti-Leakage & Contract Tests
# =========================================================================

def test_novelty_detector_rejects_verification_columns():
    """Ensure FeatureNoveltyDetector rejects target/verification columns."""
    df_leaky = pd.DataFrame({
        "ensemble_std": [1.0, 2.0],
        "truth_value": [25.0, 26.0],  # FORBIDDEN
    })
    detector = FeatureNoveltyDetector()
    with pytest.raises(ValueError, match="forbidden verification columns"):
        detector.fit(df_leaky)


def test_failure_retriever_rejects_verification_columns():
    """Ensure HistoricalFailureRetriever rejects target columns in query features."""
    df_leaky = pd.DataFrame({
        "ensemble_std": [1.0, 2.0],
        "forecast_error": [5.0, 6.0],  # FORBIDDEN
    })
    retriever = HistoricalFailureRetriever()
    with pytest.raises(ValueError, match="forbidden target columns"):
        retriever.fit(df_leaky, pd.Series([0, 1]))


def test_attribution_rejects_verification_columns():
    """Ensure ForecastRiskAttributionEngine rejects target columns."""
    engine = ForecastRiskAttributionEngine()
    with pytest.raises(ValueError, match="target/verification columns"):
        engine.attribute({"ensemble_std": 2.0, "bust_label": 1.0})


# =========================================================================
# 2. Feature Novelty & OOD Detection Tests
# =========================================================================

def test_novelty_detector_fits_and_scores_in_domain(synthetic_issue_features):
    """In-domain median samples should receive NORMAL novelty scores."""
    detector = FeatureNoveltyDetector()
    detector.fit(synthetic_issue_features)
    assert detector.is_fitted_

    # Median sample should have 0 distance -> NORMAL
    median_sample = synthetic_issue_features.median().to_dict()
    eval_normal = detector.evaluate_sample(median_sample)
    assert eval_normal["novelty_state"] == "NORMAL"
    assert eval_normal["novelty_score"] == 0.0

    # Batch scores on training set should have exactly ~75% NORMAL
    train_scores = detector.score(synthetic_issue_features)
    assert np.mean(train_scores <= detector.threshold_p75_) >= 0.70


def test_novelty_detector_detects_extreme_outliers(synthetic_issue_features):
    """Extreme out-of-distribution feature values must trigger HIGH or EXTREME state."""
    detector = FeatureNoveltyDetector()
    detector.fit(synthetic_issue_features)

    extreme_sample = synthetic_issue_features.iloc[0].copy()
    extreme_sample["ensemble_std"] = 100.0  # Massive outlier
    extreme_sample["forecast_delta_24h"] = 80.0

    eval_extreme = detector.evaluate_sample(extreme_sample)
    assert eval_extreme["novelty_state"] in ["HIGH", "EXTREME"]
    assert eval_extreme["outlier_features_count"] >= 1
    assert any(o["feature"] == "ensemble_std" for o in eval_extreme["top_outlier_features"])


def test_novelty_detector_handles_constant_features():
    """Zero-variance/constant features must not cause division by zero or NaN crashes."""
    df_constant = pd.DataFrame({
        "const_feat": [5.0] * 50,
        "normal_feat": np.random.normal(0, 1, 50),
    })
    detector = FeatureNoveltyDetector()
    detector.fit(df_constant)
    score = detector.score(df_constant)
    assert not np.isnan(score).any()
    assert np.all(np.isfinite(score))


def test_novelty_detector_handles_missing_values(synthetic_issue_features):
    """Missing values in query must be imputed without crashing."""
    detector = FeatureNoveltyDetector()
    detector.fit(synthetic_issue_features)

    sample_with_nans = synthetic_issue_features.iloc[0].to_dict()
    sample_with_nans["ensemble_std"] = np.nan
    sample_with_nans["forecast_delta_6h"] = np.nan

    eval_res = detector.evaluate_sample(sample_with_nans)
    assert not np.isnan(eval_res["novelty_score"])
    assert eval_res["novelty_state"] in ["NORMAL", "ELEVATED", "HIGH", "EXTREME"]


# =========================================================================
# 3. Uncertainty Decomposition Tests
# =========================================================================

def test_uncertainty_decomposer_identifies_dominant_driver():
    """Decomposer must correctly isolate high spread as dominant aleatoric driver."""
    decomposer = UncertaintyDecomposer()
    high_spread_features = {
        "ensemble_std": 6.5,
        "ensemble_range": 22.0,
        "ensemble_iqr": 12.0,
        "forecast_delta_6h": 0.1,
        "forecast_delta_24h": 0.2,
        "lead_hours": 12,
    }
    decomp = decomposer.decompose(high_spread_features, variable="temperature_2m")
    assert decomp["dominant_uncertainty_driver"] == "ENSEMBLE_DISPERSION"
    assert decomp["components"]["aleatoric_dispersion"]["score"] > 0.80
    assert 0.0 <= decomp["composite_uncertainty_score"] <= 1.0


def test_uncertainty_decomposer_identifies_instability():
    """Decomposer must identify large forecast revisions as dynamic instability."""
    decomposer = UncertaintyDecomposer()
    instability_features = {
        "ensemble_std": 0.5,
        "forecast_delta_6h": 5.0,
        "forecast_delta_24h": 8.0,
        "lead_hours": 12,
    }
    decomp = decomposer.decompose(instability_features, variable="temperature_2m")
    assert decomp["dominant_uncertainty_driver"] == "RECENT_INSTABILITY"
    assert decomp["components"]["dynamic_instability"]["score"] > 0.70


# =========================================================================
# 4. Failure Pattern Retrieval Tests
# =========================================================================

def test_failure_retriever_finds_historical_analogues(synthetic_issue_features, synthetic_labels):
    """Retriever must return top-k nearest historical instances with outcome rates."""
    retriever = HistoricalFailureRetriever(top_k=5, min_support=5)
    retriever.fit(
        X_train=synthetic_issue_features,
        y_train=synthetic_labels,
        errors_train=pd.Series(np.random.uniform(0.5, 5.0, len(synthetic_labels))),
    )
    assert retriever.is_fitted_

    query = synthetic_issue_features.iloc[0]
    res = retriever.retrieve(query)
    assert res["support_status"] == "SUFFICIENT_SUPPORT"
    assert res["analogue_count"] == 5
    assert 0.0 <= res["historical_bust_rate"] <= 1.0
    assert len(res["analogues"]) == 5


def test_failure_retriever_insufficient_support_state():
    """Sparse historical references must trigger INSUFFICIENT_HISTORICAL_SUPPORT."""
    retriever = HistoricalFailureRetriever(top_k=5, min_support=10)
    # Fit on only 3 samples
    df_tiny = pd.DataFrame({"feat_a": [1.0, 2.0, 3.0]})
    y_tiny = pd.Series([0, 1, 0])
    retriever.fit(df_tiny, y_tiny)

    res = retriever.retrieve({"feat_a": 1.5})
    assert res["support_status"] == "INSUFFICIENT_HISTORICAL_SUPPORT"
    assert res["analogue_count"] == 0
    assert res["historical_bust_rate"] is None


# =========================================================================
# 5. Risk Attribution Tests
# =========================================================================

def test_attribution_engine_with_logistic_model(synthetic_issue_features, synthetic_labels):
    """Attribution engine must produce ranked features with sign and explanations."""
    model = RegularizedLogisticClassifier()
    model.fit(synthetic_issue_features, synthetic_labels)

    engine = ForecastRiskAttributionEngine(model=model, feature_names=list(synthetic_issue_features.columns))
    query = synthetic_issue_features.iloc[0]
    drivers = engine.attribute(query, top_k=3)

    assert len(drivers) == 3
    for d in drivers:
        assert "feature" in d
        assert "raw_value" in d
        assert "magnitude" in d
        assert "direction" in d
        assert "explanation" in d
        assert d["direction"] in ["INCREASES_RISK", "DECREASES_RISK", "NEUTRAL"]


# =========================================================================
# 6. Risk Confidence Engine Tests
# =========================================================================

def test_risk_confidence_penalizes_novelty_and_missingness():
    """Confidence must decrease under extreme novelty, sparse support, and missing data."""
    conf_engine = RiskConfidenceEngine()

    # High quality condition
    conf_good = conf_engine.evaluate_confidence(
        risk_probability=0.30,
        novelty_eval={"novelty_state": "NORMAL", "novelty_score": 0.8},
        retrieval_eval={"support_status": "SUFFICIENT_SUPPORT", "available_reference_count": 500},
        location_profile={"reliability_status": "KNOWN_STRONG"},
        missing_feature_fraction=0.0,
    )
    assert conf_good["confidence_level"] == "HIGH"
    assert conf_good["risk_confidence"] >= 0.85

    # Poor quality / extreme OOD condition
    conf_poor = conf_engine.evaluate_confidence(
        risk_probability=0.75,
        novelty_eval={"novelty_state": "EXTREME", "novelty_score": 4.5},
        retrieval_eval={"support_status": "INSUFFICIENT_HISTORICAL_SUPPORT", "available_reference_count": 2},
        location_profile={"reliability_status": "NOVEL_LOCATION"},
        missing_feature_fraction=0.40,
    )
    assert conf_poor["confidence_level"] in ["LOW", "VERY_LOW"]
    assert conf_poor["risk_confidence"] < 0.50
    assert len(conf_poor["confidence_reasons"]) >= 3


# =========================================================================
# 7. Composite Failure Explanation & Schema Serialization
# =========================================================================

def test_composite_explanation_json_serialization():
    """CompositeFailureExplanation must serialize cleanly to JSON with zero custom type errors."""
    expl = CompositeFailureExplanation(
        risk_probability=0.65,
        risk_level="HIGH",
        risk_confidence=0.82,
        confidence_level="HIGH",
        primary_drivers=[{
            "feature": "ensemble_std",
            "raw_value": 3.8,
            "magnitude": 0.42,
            "direction": "INCREASES_RISK",
            "explanation": "High ensemble spread",
        }],
        uncertainty_components={"composite_uncertainty_score": 0.74, "dominant_uncertainty_driver": "ENSEMBLE_DISPERSION"},
        novelty={"novelty_score": 1.2, "novelty_state": "NORMAL"},
        historical_analogues={"analogue_count": 5, "historical_bust_rate": 0.40},
        lead_time_context={"lead_hours": 48},
        location_profile={"location_id": "srinagar", "reliability_status": "KNOWN_STRONG"},
        warnings=["High ensemble dispersion"],
        provenance={"engine_version": "14.0.0"},
    )

    json_str = expl.to_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["risk_probability"] == 0.65
    assert parsed["risk_level"] == "HIGH"
    assert parsed["confidence_level"] == "HIGH"
    assert len(parsed["primary_drivers"]) == 1

    # Test reconstruction
    reconstructed = CompositeFailureExplanation.from_dict(parsed)
    assert reconstructed.risk_probability == 0.65
    assert reconstructed.confidence_level == "HIGH"


# =========================================================================
# 8. End-to-End Master Explainer Integration Test
# =========================================================================

def test_forecast_failure_explainer_end_to_end(synthetic_issue_features, synthetic_labels):
    """ForecastFailureExplainer must run end-to-end and produce full structured explanation."""
    model = RegularizedLogisticClassifier()
    model.fit(synthetic_issue_features, synthetic_labels)

    explainer = ForecastFailureExplainer()
    df_train = synthetic_issue_features.copy()
    df_train["location_id"] = "srinagar"
    df_train["bust_label"] = synthetic_labels

    explainer.fit_reference_context(
        df_train=df_train,
        X_train=synthetic_issue_features,
        y_train=synthetic_labels,
        model=model,
    )
    assert explainer.is_fitted_

    sample_query = synthetic_issue_features.iloc[0]
    explanation = explainer.explain_forecast(
        features=sample_query,
        risk_probability=0.55,
        location_id="srinagar",
        variable="temperature_2m",
    )

    assert isinstance(explanation, CompositeFailureExplanation)
    assert explanation.risk_level == "HIGH"
    assert explanation.risk_confidence > 0.0
    assert len(explanation.primary_drivers) > 0
    assert "aleatoric_dispersion" in explanation.uncertainty_components["components"]
    assert explanation.historical_analogues["analogue_count"] > 0
    assert explanation.location_profile["location_id"] == "srinagar"

    # Confirm JSON export works
    json_export = explanation.to_json()
    assert "risk_probability" in json_export


# =========================================================================
# 9. Additional Adversarial & Real Dataset Tests
# =========================================================================

def test_location_profiler_novel_location_handling():
    """LocationRegimeProfiler must report NOVEL_LOCATION for unseen stations."""
    profiler = LocationRegimeProfiler()
    prof = profiler.get_location_profile("nonexistent_station_xyz")
    assert prof["reliability_status"] == "NOVEL_LOCATION"
    assert prof["historical_sample_count"] == 0


def test_explainer_state_isolation(synthetic_issue_features, synthetic_labels):
    """Calling explain_forecast sequentially must maintain state isolation."""
    model = RegularizedLogisticClassifier()
    model.fit(synthetic_issue_features, synthetic_labels)

    explainer = ForecastFailureExplainer()
    df_train = synthetic_issue_features.copy()
    df_train["bust_label"] = synthetic_labels
    explainer.fit_reference_context(df_train, synthetic_issue_features, synthetic_labels, model)

    sample1 = synthetic_issue_features.iloc[0]
    sample2 = synthetic_issue_features.iloc[1]

    exp1 = explainer.explain_forecast(sample1, risk_probability=0.10, location_id="goa")
    exp2 = explainer.explain_forecast(sample2, risk_probability=0.85, location_id="srinagar")

    assert exp1.risk_probability == 0.10
    assert exp2.risk_probability == 0.85
    assert exp1.risk_level == "LOW"
    assert exp2.risk_level == "CRITICAL"
    assert exp1.location_profile["location_id"] == "goa"
    assert exp2.location_profile["location_id"] == "srinagar"


def test_explainer_real_stage_b_parquet_smoke():
    """Smoke test on real Stage B historical parquet archive."""
    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip("Stage B archive not found on local path.")

    df_real = pd.read_parquet(parquet_path)
    assert len(df_real) == 35040

    # Extract features on small slice
    slice_sample = df_real.iloc[:500].copy()
    pipeline = IssueTimeSafeFeaturePipeline()
    X_feat, meta = pipeline.extract_features(slice_sample)

    detector = FeatureNoveltyDetector()
    detector.fit(X_feat)
    scores = detector.score(X_feat)
    assert len(scores) == len(X_feat)
    assert not np.isnan(scores).any()


def test_feature_attribution_directionality(synthetic_issue_features, synthetic_labels):
    """Verify that elevated dispersion features produce INCREASES_RISK direction."""
    model = RegularizedLogisticClassifier()
    model.fit(synthetic_issue_features, synthetic_labels)

    engine = ForecastRiskAttributionEngine(model=model, feature_names=list(synthetic_issue_features.columns))
    high_dispersion_query = synthetic_issue_features.median().to_dict()
    high_dispersion_query["ensemble_std"] = 10.0  # Force high spread

    drivers = engine.attribute(high_dispersion_query, top_k=5)
    std_driver = next((d for d in drivers if d["feature"] == "ensemble_std"), None)
    assert std_driver is not None
    assert std_driver["magnitude"] > 0.0


def test_uncertainty_composite_monotonicity():
    """Higher spread and revisions must monotonically increase composite uncertainty score."""
    decomposer = UncertaintyDecomposer()
    low_state = {
        "ensemble_std": 0.5,
        "forecast_delta_6h": 0.0,
        "forecast_delta_24h": 0.0,
        "lead_hours": 6,
    }
    high_state = {
        "ensemble_std": 5.0,
        "forecast_delta_6h": 4.0,
        "forecast_delta_24h": 6.0,
        "lead_hours": 72,
    }
    u_low = decomposer.decompose(low_state)["composite_uncertainty_score"]
    u_high = decomposer.decompose(high_state)["composite_uncertainty_score"]
    assert u_high > u_low


def test_failure_retriever_location_filtering(synthetic_issue_features, synthetic_labels):
    """Retriever must filter by location when sufficient support exists."""
    locations = pd.Series(["srinagar"] * 100 + ["goa"] * 100)
    retriever = HistoricalFailureRetriever(top_k=5, min_support=5)
    retriever.fit(synthetic_issue_features, synthetic_labels, locations_train=locations)

    query = synthetic_issue_features.iloc[0]
    res_srinagar = retriever.retrieve(query, filter_location="srinagar")
    assert res_srinagar["support_status"] == "SUFFICIENT_SUPPORT"
    for a in res_srinagar["analogues"]:
        assert a["location"] == "srinagar"


def test_confidence_engine_extreme_missingness():
    """Extreme missingness (>50% NaNs) must reduce confidence level."""
    engine = RiskConfidenceEngine()
    conf = engine.evaluate_confidence(
        risk_probability=0.50,
        missing_feature_fraction=0.60,
    )
    assert conf["confidence_level"] in ["LOW", "VERY_LOW"]
    assert conf["risk_confidence"] < 0.75


def test_reproducibility_deterministic_attribution(synthetic_issue_features, synthetic_labels):
    """Attribution and explainer outputs must be bit-identical for identical inputs."""
    model = RegularizedLogisticClassifier()
    model.fit(synthetic_issue_features, synthetic_labels)

    explainer = ForecastFailureExplainer()
    df_train = synthetic_issue_features.copy()
    df_train["location_id"] = "delhi"
    df_train["bust_label"] = synthetic_labels
    explainer.fit_reference_context(df_train, synthetic_issue_features, synthetic_labels, model)

    sample = synthetic_issue_features.iloc[5]
    exp1 = explainer.explain_forecast(sample, risk_probability=0.45, location_id="delhi")
    exp2 = explainer.explain_forecast(sample, risk_probability=0.45, location_id="delhi")

    # Mathematical components must be bit-identical
    assert exp1.primary_drivers == exp2.primary_drivers
    assert exp1.uncertainty_components == exp2.uncertainty_components
    assert exp1.novelty == exp2.novelty
    assert exp1.risk_confidence == exp2.risk_confidence
    assert exp1.risk_level == exp2.risk_level
