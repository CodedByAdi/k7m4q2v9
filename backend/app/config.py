"""Configuration and constants for the Windline application."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

# Application metadata
APP_NAME = "Windline"
APP_DESCRIPTION = "Retrospective GB Wind Generation Forecast Analytics"
VERSION = "1.0.0"

# Filesystem paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = Path(os.getenv("WINDLINE_DATA_DIR", str(REPO_ROOT / "data")))
AUDIT_DIR = DATA_DIR / "audit"
PROVENANCE_FILE = DATA_DIR / "provenance.json"

# Target domain date windows
DECISION_DATE_START = date(2026, 1, 1)
DECISION_DATE_END = date(2026, 1, 31)
DELIVERY_DATE_START = date(2026, 1, 2)
DELIVERY_DATE_END = date(2026, 2, 1)

TOTAL_DECISION_DAYS = 31
TOTAL_DELIVERY_DAYS = 31

# Standard intervals
EXPECTED_HOURLY_INTERVALS_PER_DAY = 24
TOTAL_EXPECTED_HOURLY_INTERVALS = 31 * 24  # 744

# Default cutoff time in Europe/London (HH:MM)
DEFAULT_CUTOFF_STR = "09:00"

# Timezone object
LONDON_TZ = ZoneInfo("Europe/London")
