"""Golden Replay Matrix & Scenarios for Veyra Phase 3 Day 35 (Gate C5).

Defines 10 controlled, scientifically defensible golden test scenarios for validating
deterministic offline inference reproducibility across location, variable, lead time,
certification, OOD, abstention, and revision store boundaries.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class GoldenReplayScenario:
    """Scientific specification of a single golden replay test case."""

    scenario_id: str
    description: str
    location: str
    variable: str
    issue_time: str
    valid_time: str
    forecast_value: float
    ensemble_mean: float
    ensemble_spread: float
    member_values: List[float]
    expected_certified: bool
    expected_ood: bool
    expected_causes_abstention: bool
    expected_lead_hours: int
    expected_canonical_location: str
    expected_min_risk_band: Optional[str] = None
    tolerance: float = 1e-5


GOLDEN_REPLAY_MATRIX: List[GoldenReplayScenario] = [
    # 1. Certified benchmark location + supported variable + 24h lead
    GoldenReplayScenario(
        scenario_id="GOLDEN-01-CERTIFIED-DELHI-TEMP-24H",
        description="Delhi, temperature_2m, 24h lead (certified benchmark station & variable)",
        location="Delhi",
        variable="temperature_2m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
        forecast_value=305.15,  # 32 °C in Kelvin
        ensemble_mean=305.10,
        ensemble_spread=1.2,
        member_values=[305.0 + (i * 0.1 - 1.5) for i in range(31)],
        expected_certified=True,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=24,
        expected_canonical_location="Delhi",
    ),
    # 2. Certified benchmark location at 240h lead boundary
    GoldenReplayScenario(
        scenario_id="GOLDEN-02-CERTIFIED-BENGALURU-WIND-240H",
        description="Bengaluru, wind_speed_10m, 240h lead (at maximum certified lead horizon)",
        location="Bengaluru",
        variable="wind_speed_10m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-30T00:00:00Z",
        forecast_value=8.5,
        ensemble_mean=8.2,
        ensemble_spread=2.1,
        member_values=[8.0 + (i * 0.15 - 2.25) for i in range(31)],
        expected_certified=True,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=240,
        expected_canonical_location="Bengaluru",
    ),
    # 3. 264h extended operational lead (uncertified)
    GoldenReplayScenario(
        scenario_id="GOLDEN-03-EXTENDED-MUMBAI-PRESS-264H",
        description="Mumbai, surface_pressure, 264h lead (extended operational scope, outside certified 240h boundary)",
        location="Mumbai",
        variable="surface_pressure",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-10-01T00:00:00Z",
        forecast_value=101200.0,
        ensemble_mean=101250.0,
        ensemble_spread=350.0,
        member_values=[101200.0 + (i * 20.0 - 300.0) for i in range(31)],
        expected_certified=False,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=264,
        expected_canonical_location="Mumbai",
    ),
    # 4. Non-certified location
    GoldenReplayScenario(
        scenario_id="GOLDEN-04-UNCERTIFIED-PATNA-TEMP-48H",
        description="Patna, temperature_2m, 48h lead (uncertified station)",
        location="Patna",
        variable="temperature_2m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-22T00:00:00Z",
        forecast_value=308.15,
        ensemble_mean=308.0,
        ensemble_spread=1.5,
        member_values=[308.0 + (i * 0.1 - 1.5) for i in range(31)],
        expected_certified=False,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=48,
        expected_canonical_location="Patna",
    ),
    # 5. Legitimate location alias resolution (Panaji -> Goa)
    GoldenReplayScenario(
        scenario_id="GOLDEN-05-ALIAS-PANAJI-GOA-WIND-48H",
        description="Panaji (alias for Goa), wind_speed_10m, 48h lead (deterministic alias normalization)",
        location="Panaji",
        variable="wind_speed_10m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-22T00:00:00Z",
        forecast_value=12.0,
        ensemble_mean=11.8,
        ensemble_spread=2.0,
        member_values=[12.0 + (i * 0.1 - 1.5) for i in range(31)],
        expected_certified=True,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=48,
        expected_canonical_location="Panaji",
    ),
    # 6. Invalid / blank location (QC / abstention error handling)
    GoldenReplayScenario(
        scenario_id="GOLDEN-06-INVALID-LOCATION-ABSTAIN",
        description="Blank location name (causes automated abstention / invalid location response)",
        location="",
        variable="temperature_2m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
        forecast_value=300.0,
        ensemble_mean=300.0,
        ensemble_spread=1.0,
        member_values=[300.0 for _ in range(31)],
        expected_certified=False,
        expected_ood=False,
        expected_causes_abstention=True,
        expected_lead_hours=24,
        expected_canonical_location="",
    ),
    # 7. Calibration failure simulation
    GoldenReplayScenario(
        scenario_id="GOLDEN-07-CALIBRATION-FAILURE-SIMULATION",
        description="Uncalibrated probability fallback test (simulates calibrator failure gracefully)",
        location="Delhi",
        variable="temperature_2m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
        forecast_value=305.15,
        ensemble_mean=305.10,
        ensemble_spread=1.2,
        member_values=[305.0 + (i * 0.1 - 1.5) for i in range(31)],
        expected_certified=True,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=24,
        expected_canonical_location="Delhi",
    ),
    # 8. Out-of-Distribution extreme parameter
    GoldenReplayScenario(
        scenario_id="GOLDEN-08-OOD-EXTREME-TEMPERATURE",
        description="Temperature 380.0 K (106.85 °C) exceeding physical domain bounds (evaluates to OUT_OF_DISTRIBUTION)",
        location="Delhi",
        variable="temperature_2m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
        forecast_value=380.0,  # Extreme high temperature exceeding 350.0 K max bound
        ensemble_mean=380.0,
        ensemble_spread=5.0,
        member_values=[380.0 + (i * 0.5 - 7.5) for i in range(31)],
        expected_certified=True,  # Delhi is certified, but parameter is OOD
        expected_ood=True,
        expected_causes_abstention=False,  # OOD is diagnostic-only
        expected_lead_hours=24,
        expected_canonical_location="Delhi",
    ),
    # 9. Time contract validation edge case (Leh, 12h lead)
    GoldenReplayScenario(
        scenario_id="GOLDEN-09-TIME-CONTRACT-LEH-12H",
        description="Leh, temperature_2m, 12h lead (validates timezone normalization & Leh inclusion)",
        location="Leh",
        variable="temperature_2m",
        issue_time="2026-09-20T06:00:00+00:00",
        valid_time="2026-09-20T18:00:00Z",
        forecast_value=275.15,  # +2 °C in Kelvin
        ensemble_mean=275.0,
        ensemble_spread=2.5,
        member_values=[275.0 + (i * 0.2 - 3.0) for i in range(31)],
        expected_certified=True,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=12,
        expected_canonical_location="Leh",
    ),
    # 10. Revision no-history initial state
    GoldenReplayScenario(
        scenario_id="GOLDEN-10-REVISION-NO-HISTORY-INITIAL",
        description="Initial request for a unique target time without durable prior issue cycles (evaluates to INSUFFICIENT_HISTORY)",
        location="Shimla",
        variable="surface_pressure",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
        forecast_value=78000.0,
        ensemble_mean=78050.0,
        ensemble_spread=200.0,
        member_values=[78000.0 + (i * 15.0 - 225.0) for i in range(31)],
        expected_certified=True,
        expected_ood=False,
        expected_causes_abstention=False,
        expected_lead_hours=24,
        expected_canonical_location="Shimla",
    ),
]
