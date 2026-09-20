"""Authoritative Time Contract and Temporal Validation Engine for Veyra Phase 3 Day 34 (Gate C4).

Formalizes the temporal invariant:
    lead_hours = (valid_time - issue_time) in hours

SCIENTIFIC GOVERNANCE & TIMEZONE CONTRACT:
1. Strict UTC Normalization: All timestamps are normalized to ISO 8601 UTC ('YYYY-MM-DDTHH:MM:SSZ').
2. Non-Negative & Strictly Positive Lead: valid_time must be strictly after issue_time (lead_hours >= 1).
3. Horizon Scope Separation:
   - <= 240h: Within frozen benchmark lead scope (eligible for scientific certification).
   - 264h - 384h: Extended operational horizon (valid operational inference, outside frozen certification).
   - > 384h: Rejected as unsupported forecast horizon.
4. Input Invariance: Naive timestamps without offset default to UTC; timezone offsets are converted to UTC.
"""
from datetime import datetime, timezone
import math
from typing import Optional, Tuple

MAX_SUPPORTED_LEAD_HOURS = 384
MAX_CERTIFIED_LEAD_HOURS = 240
MIN_SUPPORTED_LEAD_HOURS = 1


def parse_utc_timestamp(timestamp_str: str, field_name: str = "timestamp") -> datetime:
    """Parse and normalize an ISO 8601 timestamp string into a timezone-aware UTC datetime.

    Args:
        timestamp_str: ISO 8601 formatted timestamp string (e.g. '2026-09-20T06:00:00Z', '2026-09-20T06:00:00+00:00').
        field_name: Contextual field name for precise validation error reporting.

    Returns:
        Timezone-aware datetime object in UTC.

    Raises:
        ValueError: If timestamp string is empty, unparseable, or invalid.
    """
    if not timestamp_str or not str(timestamp_str).strip():
        raise ValueError(f"{field_name} must not be empty or whitespace.")

    clean_str = str(timestamp_str).strip()
    try:
        dt = datetime.fromisoformat(clean_str.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(
            f"Invalid {field_name} '{timestamp_str}': must be valid ISO 8601 format."
        ) from exc

    if dt.tzinfo is None:
        # Default naive timestamps to UTC per project contract
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert any timezone offset to UTC
        dt = dt.astimezone(timezone.utc)

    return dt


def format_utc_timestamp(dt: datetime) -> str:
    """Format a datetime object as a standard canonical UTC ISO 8601 string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_and_validate_lead_hours(
    issue_time: str,
    valid_time: str,
    max_lead_hours: int = MAX_SUPPORTED_LEAD_HOURS,
    min_lead_hours: int = MIN_SUPPORTED_LEAD_HOURS,
) -> Tuple[int, str, str]:
    """Derive lead_hours from issue_time and valid_time with strict temporal validation.

    Args:
        issue_time: Forecast issue cycle timestamp string.
        valid_time: Forecast target verification timestamp string.
        max_lead_hours: Upper bound for supported lead time (default 384).
        min_lead_hours: Lower bound for supported lead time (default 1).

    Returns:
        Tuple of (lead_hours: int, canonical_issue_time_utc: str, canonical_valid_time_utc: str).

    Raises:
        ValueError: On reversed timestamps, non-positive lead, non-whole hour lead, or out-of-bounds horizon.
    """
    issue_dt = parse_utc_timestamp(issue_time, "issue_time")
    valid_dt = parse_utc_timestamp(valid_time, "valid_time")

    total_seconds = (valid_dt - issue_dt).total_seconds()

    if total_seconds <= 0:
        raise ValueError(
            f"valid_time ({valid_time}) must be strictly after issue_time ({issue_time}). "
            f"Derived lead time was {total_seconds / 3600.0:.2f} hours."
        )

    lead_hours_float = total_seconds / 3600.0
    lead_hours_int = int(round(lead_hours_float))

    if abs(lead_hours_float - lead_hours_int) > 1e-4:
        raise ValueError(
            f"issue_time ({issue_time}) and valid_time ({valid_time}) must define a whole-hour lead horizon. "
            f"Derived lead time was {lead_hours_float:.4f} hours."
        )

    if lead_hours_int < min_lead_hours:
        raise ValueError(
            f"Derived lead time {lead_hours_int}h is less than the minimum supported lead of {min_lead_hours}h."
        )

    if lead_hours_int > max_lead_hours:
        raise ValueError(
            f"Derived lead time {lead_hours_int}h exceeds the maximum supported horizon of {max_lead_hours}h."
        )

    return (
        lead_hours_int,
        format_utc_timestamp(issue_dt),
        format_utc_timestamp(valid_dt),
    )


def is_certified_lead_horizon(lead_hours: int) -> bool:
    """Check whether a given lead_hours value is within the frozen benchmark certification horizon (<= 240h)."""
    return 1 <= lead_hours <= MAX_CERTIFIED_LEAD_HOURS
