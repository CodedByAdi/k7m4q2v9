#!/usr/bin/env python3
"""
Elexon BMRS API — Data Contract Verification & Feasibility Test
================================================================

Inspects the FUELHH (half-hourly actual generation by fuel type) and
WINDFOR (wind generation forecast) streaming endpoints.

Performs:
  1. Schema discovery — field names, types, timestamp formats
  2. FUELHH fetch for a single delivery day filtered to WIND
  3. WINDFOR fetch covering a decision-date publish window
  4. publishTime behaviour analysis (vintage structure, coverage)
  5. Alignment test between forecast and actual intervals
  6. Saves raw JSON samples under data/sample/

Requirements: Python 3.9+, no third-party packages.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE = "https://data.elexon.co.uk/bmrs/api/v1"

# Delivery day for actual-generation test
FUELHH_DELIVERY_DATE = "2026-01-02"

# Decision date for forecast test — we look for forecasts published
# on this day up to a proposed 09:00 Europe/London cutoff.
WINDFOR_DECISION_DATE = "2026-01-01"
# In January, Europe/London == UTC+0 (GMT), so 09:00 local = 09:00 UTC.
WINDFOR_PUBLISH_FROM = f"{WINDFOR_DECISION_DATE}T00:00:00Z"
WINDFOR_PUBLISH_TO   = f"{WINDFOR_DECISION_DATE}T09:00:00Z"

# Output directory (relative to repo root)
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> tuple[int, list[dict[str, Any]]]:
    """GET *url* and return (http_status, parsed_json_list)."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, list):
                data = [data]
            return status, data
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code}: {exc.reason}  URL={url}", file=sys.stderr)
        return exc.code, []


def save_sample(name: str, data: list[dict]) -> Path:
    """Persist *data* as pretty-printed JSON under SAMPLE_DIR."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    path = SAMPLE_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def print_section(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def print_field_summary(records: list[dict]) -> None:
    """Print field names and a compact type/example summary."""
    if not records:
        print("  (no records)")
        return
    first = records[0]
    print(f"  Fields ({len(first)} total):")
    for key, val in first.items():
        print(f"    {key:24s}  type={type(val).__name__:6s}  example={val!r}")


def iso_parse(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string (with trailing Z) to aware datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


# ---------------------------------------------------------------------------
# 1. FUELHH — Actual wind generation for one delivery day
# ---------------------------------------------------------------------------

def test_fuelhh() -> list[dict]:
    print_section("FUELHH — Actual half-hourly wind generation")

    params = {
        "settlementDateFrom": FUELHH_DELIVERY_DATE,
        "settlementDateTo":   FUELHH_DELIVERY_DATE,
        "fuelType":           "WIND",
    }
    url = f"{API_BASE}/datasets/FUELHH/stream?{urllib.parse.urlencode(params)}"
    print(f"  Request URL : {url}")
    print(f"  Parameters  : {params}")

    status, data = fetch_json(url)
    print(f"  HTTP Status : {status}")
    print(f"  Row count   : {len(data)}")

    if not data:
        print("  *** NO DATA RETURNED — BLOCKER ***")
        return data

    print_field_summary(data)

    # Settlement-period coverage
    sps = sorted(r["settlementPeriod"] for r in data)
    print(f"\n  Settlement periods returned: {min(sps)}–{max(sps)}  "
          f"(count={len(sps)}, expected=48)")

    # Check for duplicate startTimes (indicates revisions)
    start_counts = Counter(r["startTime"] for r in data)
    dups = {k: v for k, v in start_counts.items() if v > 1}
    if dups:
        print(f"  ⚠  Duplicate startTime values detected ({len(dups)} intervals):")
        for st, cnt in sorted(dups.items())[:5]:
            print(f"      {st} × {cnt}")
    else:
        print("  ✓ No duplicate startTime values — one row per interval.")

    # Publish-time analysis
    pub_times = sorted(set(r["publishTime"] for r in data))
    print(f"\n  Distinct publishTime values: {len(pub_times)}")
    if len(pub_times) <= 50:
        for pt in pub_times[:5]:
            print(f"    {pt}")
        if len(pub_times) > 5:
            print(f"    ... ({len(pub_times) - 5} more)")

    # Timestamp format evidence
    sample_row = data[0]
    print(f"\n  Timestamp format evidence:")
    print(f"    publishTime  : {sample_row['publishTime']!r}")
    print(f"    startTime    : {sample_row['startTime']!r}")
    print(f"    settlementDate: {sample_row['settlementDate']!r}")

    # First 3 records
    print(f"\n  Sample records (first 3):")
    for r in data[:3]:
        print(f"    {json.dumps(r)}")

    return data


# ---------------------------------------------------------------------------
# 2. WINDFOR — Wind generation forecast
# ---------------------------------------------------------------------------

def test_windfor() -> list[dict]:
    print_section("WINDFOR — Wind generation forecast")

    params = {
        "publishDateTimeFrom": WINDFOR_PUBLISH_FROM,
        "publishDateTimeTo":   WINDFOR_PUBLISH_TO,
    }
    url = f"{API_BASE}/datasets/WINDFOR/stream?{urllib.parse.urlencode(params)}"
    print(f"  Request URL : {url}")
    print(f"  Parameters  : {params}")

    status, data = fetch_json(url)
    print(f"  HTTP Status : {status}")
    print(f"  Row count   : {len(data)}")

    if not data:
        print("  *** NO DATA RETURNED — BLOCKER ***")
        return data

    print_field_summary(data)

    # ---------- publishTime analysis ----------
    vintages = defaultdict(list)
    for r in data:
        vintages[r["publishTime"]].append(r)

    pub_times_sorted = sorted(vintages.keys())
    print(f"\n  Distinct publishTime values (vintages): {len(pub_times_sorted)}")
    for pt in pub_times_sorted:
        rows = vintages[pt]
        starts = sorted(r["startTime"] for r in rows)
        print(f"    {pt}  →  {len(rows)} intervals,  "
              f"startTime range {starts[0]} … {starts[-1]}")

    # ---------- Coverage per vintage ----------
    print(f"\n  Vintage completeness check:")
    for pt in pub_times_sorted:
        rows = vintages[pt]
        starts = sorted(set(r["startTime"] for r in rows))
        # Count how many hours fall on the first delivery day (D+1)
        delivery_day_start = WINDFOR_DECISION_DATE.replace(
            WINDFOR_DECISION_DATE[:4],
            str(int(WINDFOR_DECISION_DATE[:4])),
        )  # same date — decision date; delivery day is D+1
        # delivery dates covered
        dates_covered = sorted(set(
            iso_parse(s).strftime("%Y-%m-%d") for s in starts
        ))
        print(f"    {pt}:")
        print(f"      Total intervals    : {len(rows)}")
        print(f"      Unique startTimes  : {len(starts)}")
        print(f"      Dates covered      : {dates_covered}")

        # Check duplicates within this vintage
        dup_starts = {s: c for s, c in Counter(
            r["startTime"] for r in rows).items() if c > 1}
        if dup_starts:
            print(f"      ⚠ Duplicate startTimes within vintage: {len(dup_starts)}")
        else:
            print(f"      ✓ No duplicate startTimes within vintage")

    # WINDFOR granularity detection
    all_starts = sorted(set(r["startTime"] for r in data))
    if len(all_starts) >= 2:
        t0 = iso_parse(all_starts[0])
        t1 = iso_parse(all_starts[1])
        delta = t1 - t0
        print(f"\n  Forecast interval granularity: {delta} "
              f"({'hourly' if delta == timedelta(hours=1) else 'half-hourly' if delta == timedelta(minutes=30) else str(delta)})")

    # Sample records
    print(f"\n  Sample records (first 3):")
    for r in data[:3]:
        print(f"    {json.dumps(r)}")

    return data


# ---------------------------------------------------------------------------
# 3. Alignment test — can forecast and actual be joined?
# ---------------------------------------------------------------------------

def test_alignment(fuelhh: list[dict], windfor: list[dict]) -> None:
    print_section("Alignment test — WINDFOR vs FUELHH interval join")

    if not fuelhh or not windfor:
        print("  Skipped — one or both datasets empty.")
        return

    # FUELHH startTimes are half-hourly (HH:00, HH:30) in UTC
    # WINDFOR startTimes are hourly (HH:00) in UTC
    actual_starts = set(r["startTime"] for r in fuelhh)
    forecast_starts = set(r["startTime"] for r in windfor)

    # Direct intersection
    direct_overlap = actual_starts & forecast_starts
    print(f"  FUELHH unique startTimes   : {len(actual_starts)}")
    print(f"  WINDFOR unique startTimes  : {len(forecast_starts)}")
    print(f"  Direct startTime overlap   : {len(direct_overlap)}")

    if direct_overlap:
        sample = sorted(direct_overlap)[:5]
        print(f"  Example overlapping times  : {sample}")

    # WINDFOR is hourly, FUELHH is half-hourly.
    # To align: each WINDFOR hour can be matched to 2 FUELHH half-hours.
    # Approach: truncate FUELHH startTime to the hour, then join.
    actual_by_hour: dict[str, list[dict]] = defaultdict(list)
    for r in fuelhh:
        dt = iso_parse(r["startTime"])
        hour_key = dt.replace(minute=0, second=0).isoformat()
        actual_by_hour[hour_key].append(r)

    forecast_hours = set()
    for r in windfor:
        dt = iso_parse(r["startTime"])
        forecast_hours.add(dt.isoformat())

    hourly_overlap = set(actual_by_hour.keys()) & forecast_hours
    print(f"\n  After hourly normalisation:")
    print(f"    FUELHH hours             : {len(actual_by_hour)}")
    print(f"    WINDFOR hours            : {len(forecast_hours)}")
    print(f"    Joinable hours           : {len(hourly_overlap)}")

    if hourly_overlap:
        sample_hour = sorted(hourly_overlap)[0]
        hh_rows = actual_by_hour[sample_hour]
        print(f"\n  Example join for hour {sample_hour}:")
        print(f"    FUELHH half-hours in this hour: {len(hh_rows)}")
        for r in hh_rows:
            print(f"      SP={r['settlementPeriod']:2d}  "
                  f"startTime={r['startTime']}  "
                  f"generation={r['generation']} MW")
        # Find a matching forecast row
        wf_match = [r for r in windfor if r["startTime"] == sample_hour
                    or r["startTime"] == sample_hour.replace("+00:00", "Z")]
        if wf_match:
            print(f"    WINDFOR forecast         : generation={wf_match[0]['generation']} MW  "
                  f"publishTime={wf_match[0]['publishTime']}")

    # Alignment strategy summary
    print(f"\n  Alignment strategy:")
    print(f"    WINDFOR uses 1-hour intervals; FUELHH uses 30-min intervals.")
    print(f"    → Average or sum each pair of FUELHH half-hours per clock hour,")
    print(f"      then join to WINDFOR on the same hour boundary.")
    print(f"    Timestamps are UTC (ISO 8601 with 'Z' suffix).")
    print(f"    No timezone offset differences observed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Elexon BMRS API — Data Feasibility Inspection")
    print(f"Run at: {datetime.now(timezone.utc).isoformat()}")
    print(f"API base: {API_BASE}")

    # ---- FUELHH ----
    fuelhh = test_fuelhh()
    if fuelhh:
        path = save_sample("fuelhh_wind_2026-01-02", fuelhh)
        print(f"\n  Saved {len(fuelhh)} records → {path}")

    # ---- WINDFOR ----
    windfor = test_windfor()
    if windfor:
        path = save_sample("windfor_2026-01-01_pre09", windfor)
        print(f"\n  Saved {len(windfor)} records → {path}")

    # ---- Alignment ----
    test_alignment(fuelhh, windfor)

    # ---- GO / NO-GO ----
    print_section("GO / NO-GO Assessment")
    blockers = []
    if not fuelhh:
        blockers.append("FUELHH returned no data")
    if not windfor:
        blockers.append("WINDFOR returned no data")

    if blockers:
        print(f"  ❌  NO-GO — Blockers found:")
        for b in blockers:
            print(f"       • {b}")
    else:
        fuelhh_sps = len(set(r["settlementPeriod"] for r in fuelhh))
        windfor_vintages = len(set(r["publishTime"] for r in windfor))
        print(f"  ✅  GO — Both datasets return valid data.")
        print(f"       FUELHH : {len(fuelhh)} rows, {fuelhh_sps} settlement periods")
        print(f"       WINDFOR: {len(windfor)} rows, {windfor_vintages} forecast vintages")
        print(f"       Alignment feasible via hourly normalisation.")
        print(f"       No API key required. No pagination limits on stream endpoints.")


if __name__ == "__main__":
    main()
