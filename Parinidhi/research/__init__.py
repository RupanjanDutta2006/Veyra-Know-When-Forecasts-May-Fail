"""
Veyra Research Suite (Phase 5B.2)
Parallel research engineering modules for conditional error distribution, trust horizon,
failure fingerprinting, decision modes, probabilistic evaluation, adversarial red-teaming,
efficiency benchmarking, product contracts, and visualization specifications.
"""
from research.error_distribution import QuantileMeshDistribution, ParametricErrorDistribution, LeadConditionedCalibrator
from research.trust_horizon import TrustHorizonEngine, TrustHorizonReport
from research.failure_fingerprint import FailureFingerprintEngine, FailureFingerprintResult
from research.decision import DecisionModeEngine, DecisionModeResult, DecisionMode
from research.evaluation import calculate_brier_skill_score, calculate_ece, calculate_pr_auc, calculate_roc_auc, FailureArchetypeEvaluator
from research.redteam import AdversarialRedTeamSuite
from research.efficiency import EfficiencyBenchmarker
from research.contract import ResearchProductResponse, ResearchToProductAdapter
from research.visualization import ResearchVisualizer

__all__ = [
    "QuantileMeshDistribution",
    "ParametricErrorDistribution",
    "LeadConditionedCalibrator",
    "TrustHorizonEngine",
    "TrustHorizonReport",
    "FailureFingerprintEngine",
    "FailureFingerprintResult",
    "DecisionModeEngine",
    "DecisionModeResult",
    "DecisionMode",
    "calculate_brier_skill_score",
    "calculate_ece",
    "calculate_pr_auc",
    "calculate_roc_auc",
    "FailureArchetypeEvaluator",
    "AdversarialRedTeamSuite",
    "EfficiencyBenchmarker",
    "ResearchProductResponse",
    "ResearchToProductAdapter",
    "ResearchVisualizer"
]
