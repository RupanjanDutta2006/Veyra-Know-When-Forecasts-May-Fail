"""
Veyra Research — Failure Fingerprint Scientific Evaluation
Evaluates meteorological failure fingerprint archetypes against empirical held-out outcomes.

SCIENTIFIC PRINCIPLE (NON-CAUSAL FRAMING):
- Fingerprints are observational diagnostic patterns and statistical associations.
- Explanations must strictly use non-causal language:
  "associated with", "consistent with", "pattern observed in", "diagnostic indicator".
- FORBIDDEN causal claims: "caused by", "proves", "guarantees".
- INSUFFICIENT_EVIDENCE / UNKNOWN is explicitly preserved as a valid epistemic state.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd

from research.contract.dataset_contract import CANONICAL_LEADS, CANONICAL_VARIABLES
from research.evaluation.validation_schemes import REGION_MAPPING_25


@dataclass
class FingerprintEmpiricalProfile:
    """Empirical behavior profile of a specific failure archetype."""
    fingerprint_id: str
    archetype_name: str
    sample_count: int
    occurrence_frequency_pct: float
    empirical_bust_rate: float
    bust_rate_ci_95: Tuple[float, float]
    enrichment_ratio_over_baseline: float
    lead_distribution: Dict[int, int]
    variable_distribution: Dict[str, int]
    regional_distribution: Dict[str, int]
    non_causal_interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FingerprintEvaluationReport:
    """Complete forensic evaluation report across all recognized fingerprint archetypes."""
    total_evaluated_samples: int
    baseline_bust_rate: float
    fingerprint_profiles: Dict[str, FingerprintEmpiricalProfile]
    unclassified_or_insufficient_evidence_count: int
    scientific_disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FailureFingerprintEvaluator:
    """
    Analyzes empirical correlation, enrichment, and geographic/temporal clustering
    of failure fingerprint archetypes without making causal claims.
    """

    KNOWN_ARCHETYPES = [
        "RAPID_REVISION_SHOCK",
        "LONG_LEAD_DECAY",
        "DIURNAL_CONVECTIVE_MISMATCH",
        "WIND_GRADIENT_SHEAR",
        "TIGHT_CLUSTER_BREAKDOWN",
        "STABLE_SYNOPTIC_CONSENSUS",
        "INSUFFICIENT_EVIDENCE",
    ]

    def __init__(self, region_mapping: Optional[Dict[str, str]] = None):
        self.region_mapping = region_mapping or REGION_MAPPING_25

    def evaluate_fingerprints(
        self,
        df_eval: pd.DataFrame,
        fingerprint_col: str = "failure_fingerprint",
        label_col: str = "bust_label",
        lead_col: str = "lead_hours",
        var_col: str = "variable",
        location_col: str = "location_id",
    ) -> FingerprintEvaluationReport:
        """
        Calculates empirical bust rates, enrichment, and multi-dimensional distributions.
        """
        if df_eval.empty:
            return FingerprintEvaluationReport(
                total_evaluated_samples=0,
                baseline_bust_rate=0.0,
                fingerprint_profiles={},
                unclassified_or_insufficient_evidence_count=0,
                scientific_disclaimer="UNVALIDATED: No samples provided.",
            )

        df = df_eval.copy()
        if fingerprint_col not in df.columns:
            df[fingerprint_col] = "INSUFFICIENT_EVIDENCE"

        total_samples = len(df)
        baseline_busts = df[label_col].sum() if label_col in df.columns else 0
        baseline_rate = float(baseline_busts / total_samples) if total_samples > 0 else 0.0

        profiles: Dict[str, FingerprintEmpiricalProfile] = {}
        insufficient_evidence_count = 0

        for fp in self.KNOWN_ARCHETYPES:
            sub = df[df[fingerprint_col] == fp]
            n_fp = len(sub)
            if fp == "INSUFFICIENT_EVIDENCE":
                insufficient_evidence_count = n_fp

            if n_fp == 0:
                profiles[fp] = FingerprintEmpiricalProfile(
                    fingerprint_id=fp,
                    archetype_name=fp.replace("_", " ").title(),
                    sample_count=0,
                    occurrence_frequency_pct=0.0,
                    empirical_bust_rate=0.0,
                    bust_rate_ci_95=(0.0, 0.0),
                    enrichment_ratio_over_baseline=0.0,
                    lead_distribution={},
                    variable_distribution={},
                    regional_distribution={},
                    non_causal_interpretation="No observed occurrences in evaluation partition.",
                )
                continue

            freq_pct = round(n_fp / total_samples * 100.0, 2)
            n_busts = int(sub[label_col].sum()) if label_col in sub.columns else 0
            fp_bust_rate = float(n_busts / n_fp)

            # Wilson score interval for binomial proportion
            z = 1.96
            denom = 1.0 + (z ** 2) / n_fp
            center = (fp_bust_rate + (z ** 2) / (2.0 * n_fp)) / denom
            half_w = (z * np.sqrt((fp_bust_rate * (1.0 - fp_bust_rate) + (z ** 2) / (4.0 * n_fp)) / n_fp)) / denom
            ci_low = max(0.0, center - half_w)
            ci_high = min(1.0, center + half_w)

            enrichment = float(fp_bust_rate / baseline_rate) if baseline_rate > 0 else 1.0

            # Disaggregated distributions
            lead_dist = sub[lead_col].value_counts().to_dict() if lead_col in sub.columns else {}
            var_dist = sub[var_col].value_counts().to_dict() if var_col in sub.columns else {}

            if location_col in sub.columns:
                sub_regions = sub[location_col].map(self.region_mapping).fillna("Other")
                reg_dist = sub_regions.value_counts().to_dict()
            else:
                reg_dist = {}

            interp = (
                f"Pattern observed in {n_fp} cases ({freq_pct}% of samples). "
                f"Statistically associated with an empirical bust rate of {fp_bust_rate:.1%} "
                f"({enrichment:.2f}x enrichment over baseline {baseline_rate:.1%}). Non-causal indicator."
            )

            profiles[fp] = FingerprintEmpiricalProfile(
                fingerprint_id=fp,
                archetype_name=fp.replace("_", " ").title(),
                sample_count=n_fp,
                occurrence_frequency_pct=freq_pct,
                empirical_bust_rate=round(fp_bust_rate, 4),
                bust_rate_ci_95=(round(ci_low, 4), round(ci_high, 4)),
                enrichment_ratio_over_baseline=round(enrichment, 3),
                lead_distribution={int(k): int(v) for k, v in lead_dist.items()},
                variable_distribution={str(k): int(v) for k, v in var_dist.items()},
                regional_distribution={str(k): int(v) for k, v in reg_dist.items()},
                non_causal_interpretation=interp,
            )

        return FingerprintEvaluationReport(
            total_evaluated_samples=total_samples,
            baseline_bust_rate=round(baseline_rate, 4),
            fingerprint_profiles=profiles,
            unclassified_or_insufficient_evidence_count=insufficient_evidence_count,
            scientific_disclaimer=(
                "All fingerprint metrics represent observational associations in the verification dataset. "
                "Enrichment ratios are statistical correlations and do NOT imply causal proof of forecast failure."
            ),
        )
