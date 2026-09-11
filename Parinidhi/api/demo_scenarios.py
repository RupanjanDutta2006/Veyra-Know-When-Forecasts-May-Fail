"""
Deterministic Demonstration Fixtures (Simulation Scenarios).

SCIENTIFIC DISCLAIMER:
These 4 scenarios are deterministic demonstration fixtures, clearly labeled as
demo/simulation scenarios. They are NOT scientific validation cases and must NOT
be presented as measured real-world performance evidence.

The demo scenarios must never be used to calculate or claim model accuracy,
calibration, recall, precision, PR-AUC, or any other scientific performance metric.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

DEMO_SCENARIOS_METADATA: List[Dict[str, Any]] = [
    {
        "scenario_id": "scenario_a_high_trust",
        "title": "Scenario A: High-Trust Synoptic Consensus",
        "location_id": "delhi",
        "city": "Delhi NCR",
        "variable": "temperature_2m",
        "lead_hours": 24,
        "intended_decision_mode": "HIGH_TRUST",
        "description": "Nominal early-lead forecast (+24h) under stable synoptic ridge with narrow ensemble spread and low revision drift.",
        "disclaimer": "Deterministic demonstration fixture clearly labeled as a demo/simulation scenario. NOT a scientific validation case.",
    },
    {
        "scenario_id": "scenario_b_long_lead_decay",
        "title": "Scenario B: Long Lead Predictability Decay",
        "location_id": "mumbai",
        "city": "Mumbai",
        "variable": "temperature_2m",
        "lead_hours": 144,
        "intended_decision_mode": "DO_NOT_RELY_SOLELY",
        "description": "Extended range forecast (+144h) exhibiting chaotic ensemble dispersion growth and structural skill loss.",
        "disclaimer": "Deterministic demonstration fixture clearly labeled as a demo/simulation scenario. NOT a scientific validation case.",
    },
    {
        "scenario_id": "scenario_c_revision_shock",
        "title": "Scenario C: Rapid Revision Inter-Cycle Shock",
        "location_id": "kolkata",
        "city": "Kolkata",
        "variable": "wind_speed_10m",
        "lead_hours": 48,
        "intended_decision_mode": "RECHECK_SOON",
        "description": "Inter-cycle forecast volatility at +48h characterized by an abrupt 6h revision shift exceeding ensemble spread.",
        "disclaimer": "Deterministic demonstration fixture clearly labeled as a demo/simulation scenario. NOT a scientific validation case.",
    },
    {
        "scenario_id": "scenario_d_severe_ood",
        "title": "Scenario D: Severe Out-of-Distribution Anomaly",
        "location_id": "srinagar",
        "city": "Srinagar (Western Himalayan)",
        "variable": "temperature_2m",
        "lead_hours": 72,
        "intended_decision_mode": "ABSTAIN",
        "description": "Extreme atmospheric anomaly exhibiting high Mahalanobis novelty distance (D_M >= 40.0), triggering epistemic abstention.",
        "disclaimer": "Deterministic demonstration fixture clearly labeled as a demo/simulation scenario. NOT a scientific validation case.",
    },
]


def generate_scenario_dataframe(scenario_id: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Generate deterministic synthetic forecast records for the requested demonstration scenario."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    current_issue = now - timedelta(hours=12)
    prior_issue_6h = current_issue - timedelta(hours=6)
    prior_issue_12h = current_issue - timedelta(hours=12)

    leads = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240]

    records = []

    if scenario_id == "scenario_a_high_trust":
        loc = "delhi"
        var = "temperature_2m"
        unit = "K"
        base_t = 302.5

        for l in leads:
            vt = current_issue + timedelta(hours=l)
            std = 0.04 + (l / 240.0) * 0.15
            # Current cycle
            records.append({
                "issue_time": current_issue.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": base_t,
                "ensemble_mean": base_t,
                "ensemble_std": std,
                "ensemble_p10": base_t - 1.28 * std,
                "ensemble_p90": base_t + 1.28 * std,
                "ensemble_range": 2.56 * std,
                "ensemble_cv": std / base_t,
                "ood_score": 1.2,
            })
            # Prior 6h cycle for same valid_time
            records.append({
                "issue_time": prior_issue_6h.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l + 6,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": base_t,
                "ensemble_mean": base_t,
                "ensemble_std": std,
                "ensemble_p10": base_t - 1.28 * std,
                "ensemble_p90": base_t + 1.28 * std,
                "ensemble_range": 2.56 * std,
                "ensemble_cv": std / base_t,
                "ood_score": 1.2,
            })

    elif scenario_id == "scenario_b_long_lead_decay":
        loc = "mumbai"
        var = "temperature_2m"
        unit = "K"
        base_t = 305.0

        for l in leads:
            vt = current_issue + timedelta(hours=l)
            std = 0.30 + ((l / 60.0) ** 2.2) * 2.5
            shift = 2.0 * (l / 100.0)
            records.append({
                "issue_time": current_issue.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": base_t + shift,
                "ensemble_mean": base_t + shift,
                "ensemble_std": std,
                "ensemble_p10": (base_t + shift) - 1.28 * std,
                "ensemble_p90": (base_t + shift) + 1.28 * std,
                "ensemble_range": 2.56 * std,
                "ensemble_cv": std / base_t,
                "ood_score": 4.0 + (l / 240.0) * 15.0,
            })
            records.append({
                "issue_time": prior_issue_6h.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l + 6,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": base_t,
                "ensemble_mean": base_t,
                "ensemble_std": std,
                "ensemble_p10": base_t - 1.28 * std,
                "ensemble_p90": base_t + 1.28 * std,
                "ensemble_range": 2.56 * std,
                "ensemble_cv": std / base_t,
                "ood_score": 4.0,
            })

    elif scenario_id == "scenario_c_revision_shock":
        loc = "kolkata"
        var = "wind_speed_10m"
        unit = "m/s"
        base_w = 6.0

        for l in leads:
            vt = current_issue + timedelta(hours=l)
            is_shock = (l == 48)
            std = 1.0
            fc_curr = base_w + (6.0 if is_shock else 0.1 * (l / 24.0))
            fc_prev = base_w

            records.append({
                "issue_time": current_issue.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": fc_curr,
                "ensemble_mean": fc_curr,
                "ensemble_std": std,
                "ensemble_p10": max(0.0, fc_curr - 1.28 * std),
                "ensemble_p90": fc_curr + 1.28 * std,
                "ensemble_range": 2.56 * std,
                "ensemble_cv": std / max(fc_curr, 1.0),
                "ood_score": 8.0 if is_shock else 3.0,
            })
            records.append({
                "issue_time": prior_issue_6h.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l + 6,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": fc_prev,
                "ensemble_mean": fc_prev,
                "ensemble_std": std,
                "ensemble_p10": max(0.0, fc_prev - 1.28 * std),
                "ensemble_p90": fc_prev + 1.28 * std,
                "ensemble_range": 2.56 * std,
                "ensemble_cv": std / max(fc_prev, 1.0),
                "ood_score": 3.0,
            })
            records.append({
                "issue_time": prior_issue_12h.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l + 12,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": fc_prev,
                "ensemble_mean": fc_prev,
                "ensemble_std": std,
                "ensemble_p10": max(0.0, fc_prev - 1.28 * std),
                "ensemble_p90": fc_prev + 1.28 * std,
                "ensemble_range": 2.56 * std,
                "ensemble_cv": std / max(fc_prev, 1.0),
                "ood_score": 3.0,
            })

    else:  # scenario_d_severe_ood
        loc = "srinagar"
        var = "temperature_2m"
        unit = "K"
        base_t = 245.0

        for l in leads:
            vt = current_issue + timedelta(hours=l)
            records.append({
                "issue_time": current_issue.isoformat(),
                "valid_time": vt.isoformat(),
                "lead_hours": l,
                "location_id": loc,
                "variable": var,
                "unit": unit,
                "forecast_value": base_t,
                "ensemble_mean": base_t,
                "ensemble_std": 14.5,
                "ensemble_p10": base_t - 18.0,
                "ensemble_p90": base_t + 18.0,
                "ensemble_range": 36.0,
                "ensemble_cv": 0.06,
                "ood_score": 58.4,  # Severe OOD >= 40.0
            })

    df = pd.DataFrame(records)
    meta = next((m for m in DEMO_SCENARIOS_METADATA if m["scenario_id"] == scenario_id), DEMO_SCENARIOS_METADATA[0])
    return df, meta
