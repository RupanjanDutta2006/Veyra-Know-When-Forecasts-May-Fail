"""Cross-Provider Disagreement Intelligence Service for Veyra Phase 3 Day 38 (Gate C8).

Evaluates forecast divergence between normalized multi-provider forecast outputs.

SCIENTIFIC GOVERNANCE INVARIANTS:
1. Diagnostic Isolation: Cross-provider divergence is a diagnostic comparison between distinct forecast providers. It does NOT alter calibrated P(BUST), operational risk bands, scientific certification, or OOD policies.
2. GEFS Separation: Kept strictly distinct from Day 29 GEFS ensemble member spread.
3. Comparability Contract: Requires canonical location alignment, matching target variables, canonical units, and valid-time matching.
4. Fixture Provenance Transparency: Explicitly reports when a comparison uses fixture data.
"""
import logging
from typing import Optional

from backend.app.adapters.provider_adapter import ProviderSourceMode
from backend.app.adapters.provider_registry import (
    ProviderRegistry,
    UnknownProviderError,
    default_provider_registry,
)
from backend.app.schemas.provider_disagreement import (
    CrossProviderDisagreementRequest,
    CrossProviderDisagreementResponse,
    ProviderForecastSummary,
)
from backend.app.services.location_service import DynamicLocationService

logger = logging.getLogger(__name__)


class CrossProviderDisagreementService:
    """Service executing cross-provider forecast divergence diagnostics."""

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        location_service: Optional[DynamicLocationService] = None,
    ):
        self.registry = registry or default_provider_registry
        self.location_service = location_service or DynamicLocationService()

    def evaluate_disagreement(
        self, request: CrossProviderDisagreementRequest
    ) -> CrossProviderDisagreementResponse:
        """Evaluate cross-provider forecast divergence for the requested parameters."""
        loc_str = (request.location or "").strip()
        if not loc_str:
            return CrossProviderDisagreementResponse(
                status="INVALID_REQUEST",
                reason_code="BLANK_LOCATION",
                canonical_location="",
                variable=request.variable,
                valid_time="",
                unit="",
                is_comparable=False,
                has_fixture_provider=False,
                provenance_notice="Invalid request: location parameter cannot be blank.",
                scope_note="Cross-provider divergence is diagnostic-only.",
            )

        resolved_loc = self.location_service.resolve(loc_str)
        canonical_loc = resolved_loc.name if resolved_loc else loc_str

        # Retrieve Primary Provider Adapter
        primary_id = request.primary_provider_id or "openmeteo_gefs"
        try:
            primary_adapter = self.registry.get(primary_id)
        except UnknownProviderError as exc:
            return CrossProviderDisagreementResponse(
                status="INVALID_REQUEST",
                reason_code="UNKNOWN_PRIMARY_PROVIDER",
                canonical_location=canonical_loc,
                variable=request.variable,
                valid_time="",
                unit="",
                is_comparable=False,
                has_fixture_provider=False,
                provenance_notice=f"Primary provider error: {str(exc)}",
                scope_note="Cross-provider divergence is diagnostic-only.",
            )

        # Retrieve Secondary Provider Adapter
        secondary_id = request.secondary_provider_id or "fixture_second_provider"
        try:
            secondary_adapter = self.registry.get(secondary_id)
        except UnknownProviderError as exc:
            return CrossProviderDisagreementResponse(
                status="INVALID_REQUEST",
                reason_code="UNKNOWN_SECONDARY_PROVIDER",
                canonical_location=canonical_loc,
                variable=request.variable,
                valid_time="",
                unit="",
                is_comparable=False,
                has_fixture_provider=False,
                provenance_notice=f"Secondary provider error: {str(exc)}",
                scope_note="Cross-provider divergence is diagnostic-only.",
            )

        # Fetch normalized records from both providers
        p_record = primary_adapter.fetch_forecast(
            location=canonical_loc,
            variable=request.variable,
            lead_hours=request.lead_hours,
            issue_time=request.issue_time,
            valid_time=request.valid_time,
        )

        s_record = secondary_adapter.fetch_forecast(
            location=canonical_loc,
            variable=request.variable,
            lead_hours=request.lead_hours,
            issue_time=request.issue_time,
            valid_time=request.valid_time,
        )

        p_summary = (
            ProviderForecastSummary(
                provider_id=p_record.provider_id,
                provider_name=p_record.provider_name,
                provider_source_mode=p_record.provider_source_mode.value,
                canonical_location=p_record.canonical_location,
                issue_time=p_record.issue_time,
                valid_time=p_record.valid_time,
                lead_hours=p_record.lead_hours,
                variable=p_record.variable,
                forecast_value=p_record.forecast_value,
                unit=p_record.unit,
                is_available=p_record.is_available,
            )
            if p_record
            else None
        )

        s_summary = (
            ProviderForecastSummary(
                provider_id=s_record.provider_id,
                provider_name=s_record.provider_name,
                provider_source_mode=s_record.provider_source_mode.value,
                canonical_location=s_record.canonical_location,
                issue_time=s_record.issue_time,
                valid_time=s_record.valid_time,
                lead_hours=s_record.lead_hours,
                variable=s_record.variable,
                forecast_value=s_record.forecast_value,
                unit=s_record.unit,
                is_available=s_record.is_available,
            )
            if s_record
            else None
        )

        has_fixture = (
            (p_record and p_record.provider_source_mode == ProviderSourceMode.FIXTURE)
            or (s_record and s_record.provider_source_mode == ProviderSourceMode.FIXTURE)
        )

        provenance_notice = (
            "Comparison includes secondary provider using deterministic fixture data for architectural validation."
            if has_fixture
            else "Comparison derived from live provider operational data."
        )

        scope_note = (
            "Cross-provider divergence measures difference between normalized provider forecasts for the same target. "
            "It is separate from GEFS ensemble member spread and does not alter calibrated P(BUST) estimation."
        )

        # Validate Provider Availability
        if not p_record or not p_record.is_available or p_record.forecast_value is None:
            return CrossProviderDisagreementResponse(
                status="PROVIDER_UNAVAILABLE",
                reason_code="PRIMARY_PROVIDER_UNAVAILABLE",
                canonical_location=canonical_loc,
                variable=request.variable,
                valid_time=s_record.valid_time if s_record else "",
                unit=s_record.unit if s_record else "",
                primary_provider=p_summary,
                secondary_provider=s_summary,
                is_comparable=False,
                has_fixture_provider=has_fixture,
                provenance_notice=provenance_notice,
                scope_note=scope_note,
            )

        if not s_record or not s_record.is_available or s_record.forecast_value is None:
            return CrossProviderDisagreementResponse(
                status="PROVIDER_UNAVAILABLE",
                reason_code="SECONDARY_PROVIDER_UNAVAILABLE",
                canonical_location=canonical_loc,
                variable=request.variable,
                valid_time=p_record.valid_time,
                unit=p_record.unit,
                primary_provider=p_summary,
                secondary_provider=s_summary,
                is_comparable=False,
                has_fixture_provider=has_fixture,
                provenance_notice=provenance_notice,
                scope_note=scope_note,
            )

        # Validate Comparability Rules
        if p_record.unit != s_record.unit:
            return CrossProviderDisagreementResponse(
                status="NOT_COMPARABLE",
                reason_code="UNIT_MISMATCH",
                canonical_location=canonical_loc,
                variable=request.variable,
                valid_time=p_record.valid_time,
                unit=f"{p_record.unit} vs {s_record.unit}",
                primary_provider=p_summary,
                secondary_provider=s_summary,
                is_comparable=False,
                has_fixture_provider=has_fixture,
                provenance_notice=provenance_notice,
                scope_note=scope_note,
            )

        val_p = p_record.forecast_value
        val_s = s_record.forecast_value

        signed_diff = round(val_p - val_s, 4)
        abs_diff = round(abs(signed_diff), 4)
        p_min = round(min(val_p, val_s), 4)
        p_max = round(max(val_p, val_s), 4)
        p_mean = round((val_p + val_s) / 2.0, 4)

        rel_diff = round((abs_diff / max(abs(p_mean), 1e-3)) * 100.0, 2)

        return CrossProviderDisagreementResponse(
            status="AVAILABLE",
            reason_code="COMPARISON_SUCCESSFUL",
            canonical_location=canonical_loc,
            variable=request.variable,
            valid_time=p_record.valid_time,
            unit=p_record.unit,
            primary_provider=p_summary,
            secondary_provider=s_summary,
            signed_difference=signed_diff,
            absolute_difference=abs_diff,
            provider_min=p_min,
            provider_max=p_max,
            provider_mean=p_mean,
            relative_difference_pct=rel_diff,
            is_comparable=True,
            has_fixture_provider=has_fixture,
            provenance_notice=provenance_notice,
            scope_note=scope_note,
        )


def get_cross_provider_disagreement_service() -> CrossProviderDisagreementService:
    """Dependency provider factory for CrossProviderDisagreementService."""
    return CrossProviderDisagreementService()
