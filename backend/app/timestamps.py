"""Timestamp parsing, timezone conversion, and cutoff handling."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.app.config import (
    DELIVERY_DATE_END,
    DELIVERY_DATE_START,
    DECISION_DATE_END,
    DECISION_DATE_START,
    LONDON_TZ,
)

_CUTOFF_REGEX = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_iso_utc(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string into a timezone-aware UTC datetime.
    
    Treats 'Z' suffix as UTC. Raises ValueError on invalid format or naive timestamp.
    """
    if not isinstance(ts, str) or not ts.strip():
        raise ValueError(f"Invalid timestamp: {ts!r}")
    
    clean_ts = ts.strip()
    if clean_ts.endswith("Z"):
        clean_ts = clean_ts[:-1] + "+00:00"
    
    dt = datetime.fromisoformat(clean_ts)
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp {ts!r} lacks timezone offset (naive datetime rejected)")
    
    return dt.astimezone(timezone.utc)


def to_utc_iso(dt: datetime) -> str:
    """Format a timezone-aware datetime to standard ISO-8601 UTC string with 'Z' suffix."""
    if dt.tzinfo is None:
        raise ValueError(f"Datetime {dt!r} is naive, cannot format as UTC ISO")
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_cutoff_format(cutoff_str: str) -> tuple[int, int]:
    """Validate that cutoff_str matches 'HH:MM' (00:00 to 23:59).
    
    Returns (hour, minute) integers. Raises ValueError on invalid input.
    """
    if not isinstance(cutoff_str, str):
        raise ValueError("Cutoff must be a string")
    
    clean = cutoff_str.strip()
    match = _CUTOFF_REGEX.match(clean)
    if not match:
        raise ValueError(f"Invalid cutoff format: '{cutoff_str}'. Expected 'HH:MM' (00:00 to 23:59)")
    
    return int(match.group(1)), int(match.group(2))


def make_cutoff_datetime(decision_date: date, cutoff_str: str) -> datetime:
    """Construct the timezone-aware cutoff datetime for a decision date in Europe/London,
    then return it normalized to UTC.
    """
    hour, minute = validate_cutoff_format(cutoff_str)
    
    # In January, Europe/London is GMT (UTC+0).
    # Construct in London timezone so DST transitions would also be handled correctly if applied to other months.
    dt_local = datetime(
        year=decision_date.year,
        month=decision_date.month,
        day=decision_date.day,
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
        tzinfo=LONDON_TZ,
    )
    return dt_local.astimezone(timezone.utc)


def parse_date_str(date_str: str) -> date:
    """Parse a date string formatted as 'YYYY-MM-DD'. Raises ValueError on invalid format."""
    if not isinstance(date_str, str) or not _DATE_REGEX.match(date_str.strip()):
        raise ValueError(f"Invalid date format: {date_str!r}. Expected 'YYYY-MM-DD'")
    return date.fromisoformat(date_str.strip())


def decision_date_to_delivery_date(d: date) -> date:
    """Map decision date D to delivery date D+1."""
    return d + timedelta(days=1)


def delivery_date_to_decision_date(d: date) -> date:
    """Map delivery date D to decision date D-1."""
    return d - timedelta(days=1)


def is_valid_delivery_date(d: date) -> bool:
    """Check if date falls within the target January delivery window (2026-01-02 to 2026-02-01)."""
    return DELIVERY_DATE_START <= d <= DELIVERY_DATE_END


def is_valid_decision_date(d: date) -> bool:
    """Check if date falls within the target January decision window (2026-01-01 to 2026-01-31)."""
    return DECISION_DATE_START <= d <= DECISION_DATE_END
