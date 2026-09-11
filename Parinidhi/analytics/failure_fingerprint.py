"""
Veyra Post-Verification Failure Fingerprint Engine.

Provides analytical, post-hoc characterization of verified forecast failures / busts.
Classifies the primary structural mechanism:
1. Intensity / Magnitude Bust: Large realized amplitude error exceeding operational threshold.
2. Timing / Phase Shift Bust: The forecast trajectory shifted temporally (earlier/later onset).
3. Under-Dispersion Bust: Truth fell strictly outside the full multi-member ensemble envelope.
4. Directional Bias: Strong systematic over- or under-forecast.

SCIENTIFIC INVARIANT:
This module is strictly a POST-VERIFICATION diagnostic analysis tool.
Realized error / verification truth is NEVER leaked into issue-time prediction features.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class FailureFingerprintEngine:
    """
    Analyzes verified forecast-truth pairs to classify failure modes and root mechanisms.
    """

    @staticmethod
    def fingerprint_record(
        forecast_value: float,
        truth_value: float,
        ensemble_min: float,
        ensemble_max: float,
        ensemble_std: float,
        threshold: float,
        prev_lead_forecast: Optional[float] = None,
        next_lead_forecast: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Classify failure characteristics for a single verified forecast point.

        Args:
            forecast_value: NWP control forecast value.
            truth_value: Observed verification reference value.
            ensemble_min: Minimum value across ensemble members.
            ensemble_max: Maximum value across ensemble members.
            ensemble_std: Standard deviation across ensemble members.
            threshold: Bust error threshold.
            prev_lead_forecast: Forecast value at V - 3h (if available).
            next_lead_forecast: Forecast value at V + 3h (if available).

        Returns:
            Dictionary containing failure mode flags and dominant classification.
        """
        abs_error = abs(forecast_value - truth_value)
        is_bust = bool(abs_error >= threshold)

        # 1. Under-dispersion / Envelope Escape
        is_outside_envelope = bool(truth_value < ensemble_min or truth_value > ensemble_max)
        envelope_escape_dist = 0.0
        if truth_value < ensemble_min:
            envelope_escape_dist = float(ensemble_min - truth_value)
        elif truth_value > ensemble_max:
            envelope_escape_dist = float(truth_value - ensemble_max)

        # 2. Intensity / Extreme Magnitude Error
        is_intensity_bust = bool(abs_error >= 1.75 * threshold)

        # 3. Timing / Phase Shift
        is_timing_bust = False
        timing_shift_direction = "NONE"
        if prev_lead_forecast is not None and abs(prev_lead_forecast - truth_value) < 0.5 * abs_error:
            is_timing_bust = True
            timing_shift_direction = "EARLIER_PHASE"
        elif next_lead_forecast is not None and abs(next_lead_forecast - truth_value) < 0.5 * abs_error:
            is_timing_bust = True
            timing_shift_direction = "LATER_PHASE"

        # 4. Directional Bias
        signed_error = forecast_value - truth_value
        direction = "OVER_FORECAST" if signed_error > 0 else "UNDER_FORECAST"

        # 5. Dominant Failure Mode Determination
        if not is_bust:
            dominant_mode = "NORMAL_ACCURACY"
        elif is_timing_bust:
            dominant_mode = f"TIMING_PHASE_SHIFT ({timing_shift_direction})"
        elif is_intensity_bust and is_outside_envelope:
            dominant_mode = "COMPOUND_INTENSITY_UNDERDISPERSION"
        elif is_outside_envelope:
            dominant_mode = "ENSEMBLE_UNDERDISPERSION"
        elif is_intensity_bust:
            dominant_mode = "INTENSITY_AMPLITUDE_BUST"
        else:
            dominant_mode = f"STANDARD_QUANTILE_BUST ({direction})"

        return {
            "is_bust": is_bust,
            "abs_error": round(abs_error, 4),
            "threshold": round(threshold, 4),
            "dominant_failure_mode": dominant_mode,
            "is_underdispersion_bust": is_outside_envelope,
            "envelope_escape_distance": round(envelope_escape_dist, 4),
            "is_intensity_bust": is_intensity_bust,
            "is_timing_bust": is_timing_bust,
            "timing_shift": timing_shift_direction,
            "directional_bias": direction,
        }

    @staticmethod
    def fingerprint_batch(df_paired: pd.DataFrame, threshold_col: str = "bust_threshold") -> pd.DataFrame:
        """
        Apply failure fingerprint classification across a paired historical dataset.
        """
        df = df_paired.copy()
        if "forecast_value" not in df.columns:
            df["forecast_value"] = df.get("value", 0.0)
        if "truth_value" not in df.columns:
            raise ValueError("Required column 'truth_value' not found in paired dataframe.")

        ens_min = df.get("ensemble_min", df["forecast_value"]).astype(float)
        ens_max = df.get("ensemble_max", df["forecast_value"]).astype(float)
        ens_std = df.get("ensemble_std", pd.Series(0.0, index=df.index)).astype(float)
        fc = df["forecast_value"].astype(float)
        truth = df["truth_value"].astype(float)
        thresh = df[threshold_col].astype(float) if threshold_col in df.columns else pd.Series(2.5, index=df.index)

        abs_err = (fc - truth).abs()
        is_bust = (abs_err >= thresh).astype(int)

        is_underdisp = ((truth < ens_min) | (truth > ens_max)).astype(int)
        is_intensity = (abs_err >= 1.75 * thresh).astype(int)

        df["is_bust"] = is_bust
        df["is_underdispersion_bust"] = is_underdisp
        df["is_intensity_bust"] = is_intensity

        return df
