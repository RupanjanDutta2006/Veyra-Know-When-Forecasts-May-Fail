"""
Tests for Track 8, 9, 10: Efficiency, Product Contract, and Visualization
"""
import pytest
import numpy as np
from research.efficiency.benchmarker import EfficiencyBenchmarker
from research.contract.product_contract import ResearchProductResponse, ResearchToProductAdapter
from research.visualization.visualizers import ResearchVisualizer


def test_efficiency_benchmarker():
    def mock_predict(inp):
        return float(inp.get("x", 1.0) * 2.0)

    res = EfficiencyBenchmarker.benchmark_inference_latency(mock_predict, {"x": 5.0}, n_warmup=10, n_iterations=100)
    assert "latency_mean_ms" in res
    assert res["latency_mean_ms"] >= 0.0
    assert res["throughput_instances_per_sec"] > 0.0

    mem_res = EfficiencyBenchmarker.benchmark_memory_footprint(lambda: [i * 2 for i in range(1000)])
    assert "peak_memory_kb" in mem_res


def test_product_contract_and_adapter():
    resp = ResearchProductResponse(
        bust_probability=0.32,
        risk_level="MODERATE",
        confidence_index=0.78,
        uncertainty_pct=14.5,
        trust_horizon=144,
        ood_distance=1.2,
        stability=0.88,
        revision=0.45,
        structural_overconfidence=0.12,
        failure_fingerprint="ENSEMBLE_DIVERGENCE",
        dominant_risk_drivers=["Elevated Spread", "Gradient Shear"],
        decision_mode="CAUTION",
        abstain=False,
        reason_codes=["MODERATE_BUST_PROBABILITY", "APPROACHING_TRUST_HORIZON"]
    )

    d = resp.to_dict()
    assert d["bust_probability"] == 0.32
    assert d["decision_mode"] == "CAUTION"

    # Adapter to production V2
    v2_payload = ResearchToProductAdapter.to_production_v2_payload(resp)
    assert "bust_probability" in v2_payload
    assert "risk_level" in v2_payload
    assert v2_payload["risk_level"] == "MODERATE"
    assert "recommendation" in v2_payload
    assert "CAUTION" in v2_payload["recommendation"]


def test_research_visualizer_specs():
    leads = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240]
    probs = [0.10, 0.15, 0.22, 0.30, 0.40, 0.52, 0.65, 0.72, 0.80, 0.88]

    # Chart 1: Prob vs lead
    c1 = ResearchVisualizer.build_prob_vs_lead_spec(leads, probs)
    assert c1["chart_type"] == "line_with_band"
    assert len(c1["x_axis"]["values"]) == 10

    # Chart 2: Trust horizon timeline
    c2 = ResearchVisualizer.build_trust_horizon_timeline_spec(leads, probs, h_rel=120, h_skill_clim=168)
    assert c2["chart_type"] == "horizon_timeline"
    assert len(c2["markers"]) == 2

    # Chart 7: Failure fingerprint radar
    c7 = ResearchVisualizer.build_failure_fingerprint_radar_spec({
        "ENSEMBLE_DIVERGENCE": 0.85,
        "LONG_LEAD_DECAY": 0.30,
        "REVISION_INSTABILITY": 0.65,
        "WIND_GRADIENT_SHEAR": 0.10,
        "SYNOPTIC_TRANSITION": 0.20,
        "OOD_CONDITION": 0.05
    })
    assert c7["chart_type"] == "radar"
    assert len(c7["categories"]) == 6
