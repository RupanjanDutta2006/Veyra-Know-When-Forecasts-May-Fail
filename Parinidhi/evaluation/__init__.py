"""
Veyra Evaluation, Generalization & Decision Intelligence Framework.

Provides:
- LocationHeldOutSplitter, ClimateHeldOutSplitter, HeldOutSplit: Splitting engines.
- GeneralizationMetrics: Classification, probabilistic, and risk-utility metrics.
- GeneralizationEvaluator, GeneralizationResult: Cross-validation orchestrator.
- ProbabilityCalibrator, ReliabilityAnalyzer: Train-only calibration & reliability analysis.
- EmpiricalEvidenceEngine, EmpiricalExperimentManifest: Full empirical benchmark orchestration.
- FeatureNoveltyDetector: Leakage-safe feature-space novelty and OOD detector.
- UncertaintyDecomposer: Operational uncertainty decomposition.
- HistoricalFailureRetriever: Leakage-safe historical analogue and failure pattern retrieval.
- ForecastRiskAttributionEngine: Deterministic feature risk attribution.
- LocationRegimeProfiler: Station and meteorological regime reliability profiles.
- RiskConfidenceEngine: Self-confidence and risk-confidence quantification.
- CompositeFailureExplanation, ForecastFailureExplainer: Master failure explanation pipeline.
- ForecastRiskDecisionEngine: Master operational forecast-risk decision engine (Day 15).
- ForecastRiskDecision, RiskDecisionPolicy, ParameterGovernanceClass, ParameterMetadata: Decision schemas and policies.
- PolicyBenchmarkEvaluator, PolicyBenchmarkSummary: Policy benchmarking and expected cost evaluation.
- ThresholdSensitivityAnalyzer, DecisionSensitivityAnalyzer: Threshold perturbation and margin analyzer.
- EvidenceFusionEngine, AbstentionController, DataQualityAuditor: Evidence fusion & safety controllers.
"""

from evaluation.abstention import AbstentionController
from evaluation.attribution import ForecastRiskAttributionEngine
from evaluation.calibration import ProbabilityCalibrator, ReliabilityAnalyzer
from evaluation.data_quality import DataQualityAuditor
from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_policy import ParameterGovernanceClass, ParameterMetadata, RiskDecisionPolicy
from evaluation.decision_policy_evaluator import PolicyBenchmarkEvaluator, PolicyBenchmarkSummary
from evaluation.decision_schema import (
    DataQualityState,
    EvidenceItem,
    ForecastRiskDecision,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from evaluation.decision_sensitivity import DecisionSensitivityAnalyzer, ThresholdSensitivityAnalyzer
from evaluation.empirical_engine import EmpiricalEvidenceEngine, EmpiricalExperimentManifest
from evaluation.evidence_fusion import EvidenceFusionEngine
from evaluation.explanation_engine import ForecastFailureExplainer
from evaluation.explanation_schema import CompositeFailureExplanation
from evaluation.failure_patterns import HistoricalFailureRetriever
from evaluation.generalization import GeneralizationEvaluator, GeneralizationResult, compute_dataset_content_hash
from evaluation.metrics import GeneralizationMetrics
from evaluation.novelty import FeatureNoveltyDetector
from evaluation.profiles import LocationRegimeProfiler
from evaluation.risk_confidence import RiskConfidenceEngine
from evaluation.splits import ClimateHeldOutSplitter, HeldOutSplit, LocationHeldOutSplitter
from evaluation.uncertainty import UncertaintyDecomposer
from evaluation.trajectory_schema import (
    ForecastTrajectory,
    ForecastTrajectoryPoint,
    TrajectoryAssessment,
    TrajectoryState,
    WarningHorizon,
)
from evaluation.temporal_features import TemporalFeatureExtractor
from evaluation.instability_detector import ForecastInstabilityDetector, InstabilitySignal
from evaluation.trajectory_state_machine import TrajectoryStateMachine
from evaluation.time_to_risk import TimeToCriticalRiskEstimator, TimeToRiskEstimate
from evaluation.early_warning_score import TemporalEarlyWarningScore
from evaluation.trajectory_analogues import HistoricalTrajectoryRetriever
from evaluation.event_evaluation import EventEvaluationSummary, EventLevelEvaluator, WarningHysteresisFilter
from evaluation.temporal_early_warning_engine import TemporalEarlyWarningEngine
from evaluation.xai_schema import (
    CanonicalXAIExplanation,
    DecisionCounterfactual,
    DecisionRationale,
    DriverCategory,
    DriverDirection,
    EvidenceConflictItem,
    ExplanationLevel,
    ExplanationMode,
    FeatureRiskDriver,
    HistoricalEvidenceAlignment,
    HistoricalEvidenceExplanation,
    NoveltyExplanation,
    TemporalDynamicsExplanation,
    UncertaintyExplanation,
    UncertaintySource,
)
from evaluation.xai_attribution import XAIAttributionEngine
from evaluation.xai_counterfactual import DecisionCounterfactualGenerator
from evaluation.xai_renderer import XAIRenderer
from evaluation.xai_engine import ExplainableForecastEngine
from evaluation.event_schema import (
    EventEvaluationMetrics,
    EventLifecycleState,
    EventOutcome,
    EventOutcomeStatus,
    EventSeverity,
    EventSimilarityMatch,
    EventStateTransition,
    EventTrajectorySnapshot,
    OperationalEvent,
    OperationalUrgency,
)
from evaluation.event_tracker import EventLifecycleStateMachine, OperationalEventTracker
from evaluation.event_memory import EventMemoryStore
from evaluation.event_outcome import EventOutcomeEvaluator
from evaluation.event_intelligence import EventIntelligenceOrchestrator
from evaluation.unified_schema import (
    AssessmentStatus,
    SignalOverrideRecord,
    SignalPrecedenceTier,
    UnifiedOperationalAssessment,
)
from evaluation.signal_arbitration import SignalArbitrationEngine
from evaluation.operational_intelligence_pipeline import UnifiedOperationalRiskEngine
from evaluation.operational_trace_schema import (
    ArbitrationSummary,
    AuditValidationResult,
    AuditValidationState,
    CompletenessStatus,
    CycleChangeSummary,
    DecisionReconstruction,
    DecisionSnapshot,
    DecisionStabilityState,
    OperationalTrace,
    PostHocOutcomeRecord,
    SubsystemSignalsSummary,
    TraceIdentity,
)
from evaluation.decision_stability import CycleChangeDetector, DecisionStabilityAnalyzer
from evaluation.decision_audit import DecisionAuditValidator
from evaluation.operational_observability import OperationalObservabilityEngine

__all__ = [
    "HeldOutSplit",
    "LocationHeldOutSplitter",
    "ClimateHeldOutSplitter",
    "GeneralizationMetrics",
    "GeneralizationEvaluator",
    "GeneralizationResult",
    "compute_dataset_content_hash",
    "ProbabilityCalibrator",
    "ReliabilityAnalyzer",
    "EmpiricalEvidenceEngine",
    "EmpiricalExperimentManifest",
    "FeatureNoveltyDetector",
    "UncertaintyDecomposer",
    "HistoricalFailureRetriever",
    "ForecastRiskAttributionEngine",
    "LocationRegimeProfiler",
    "RiskConfidenceEngine",
    "CompositeFailureExplanation",
    "ForecastFailureExplainer",
    "ForecastRiskDecisionEngine",
    "ForecastRiskDecision",
    "RiskDecisionPolicy",
    "ParameterGovernanceClass",
    "ParameterMetadata",
    "PolicyBenchmarkEvaluator",
    "PolicyBenchmarkSummary",
    "ThresholdSensitivityAnalyzer",
    "RiskLevel",
    "OperationalDecision",
    "WarningPriority",
    "DataQualityState",
    "DataQualityAuditResult",
    "DataQualityAuditor",
    "EvidenceItem",
    "EvidenceFusionEngine",
    "AbstentionController",
    "DecisionSensitivityResult",
    "DecisionSensitivityAnalyzer",
    "TrajectoryState",
    "WarningHorizon",
    "ForecastTrajectoryPoint",
    "ForecastTrajectory",
    "TrajectoryAssessment",
    "TemporalFeatureExtractor",
    "ForecastInstabilityDetector",
    "InstabilitySignal",
    "TrajectoryStateMachine",
    "TimeToCriticalRiskEstimator",
    "TimeToRiskEstimate",
    "TemporalEarlyWarningScore",
    "HistoricalTrajectoryRetriever",
    "EventEvaluationSummary",
    "WarningHysteresisFilter",
    "EventLevelEvaluator",
    "TemporalEarlyWarningEngine",
    "CanonicalXAIExplanation",
    "ExplanationMode",
    "ExplanationLevel",
    "DriverCategory",
    "DriverDirection",
    "UncertaintySource",
    "HistoricalEvidenceAlignment",
    "FeatureRiskDriver",
    "UncertaintyExplanation",
    "NoveltyExplanation",
    "HistoricalEvidenceExplanation",
    "EvidenceConflictItem",
    "TemporalDynamicsExplanation",
    "DecisionRationale",
    "DecisionCounterfactual",
    "XAIAttributionEngine",
    "DecisionCounterfactualGenerator",
    "XAIRenderer",
    "ExplainableForecastEngine",
    "EventLifecycleState",
    "EventSeverity",
    "OperationalUrgency",
    "EventOutcomeStatus",
    "EventStateTransition",
    "EventTrajectorySnapshot",
    "EventSimilarityMatch",
    "EventOutcome",
    "OperationalEvent",
    "EventEvaluationMetrics",
    "EventLifecycleStateMachine",
    "OperationalEventTracker",
    "EventMemoryStore",
    "EventOutcomeEvaluator",
    "EventIntelligenceOrchestrator",
    "AssessmentStatus",
    "SignalPrecedenceTier",
    "SignalOverrideRecord",
    "UnifiedOperationalAssessment",
    "SignalArbitrationEngine",
    "UnifiedOperationalRiskEngine",
    "CompletenessStatus",
    "DecisionStabilityState",
    "AuditValidationState",
    "TraceIdentity",
    "DecisionSnapshot",
    "SubsystemSignalsSummary",
    "ArbitrationSummary",
    "CycleChangeSummary",
    "AuditValidationResult",
    "DecisionReconstruction",
    "PostHocOutcomeRecord",
    "OperationalTrace",
    "CycleChangeDetector",
    "DecisionStabilityAnalyzer",
    "DecisionAuditValidator",
    "OperationalObservabilityEngine",
]
