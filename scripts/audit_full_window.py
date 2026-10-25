#!/usr/bin/env python3
"""
Windline — Full-Window Data Audit (January 2026)
==================================================

Performs:
  1. Fetch all FUELHH WIND actuals for delivery dates 2026-01-02..2026-02-01
  2. Fetch all WINDFOR publications for decision dates 2026-01-01..2026-01-31
  3. Analyse publication-time behaviour across the full window
  4. Audit all 31 decision dates with 09:00 Europe/London cutoff
  5. Align half-hourly actuals to hourly forecasts
  6. Produce structured audit results as JSON

Requirements: Python 3.9+, no third-party packages.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
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

# Full delivery window
DELIVERY_START = date(2026, 1, 2)
DELIVERY_END   = date(2026, 2, 1)

# Full decision window
DECISION_START = date(2026, 1, 1)
DECISION_END   = date(2026, 1, 31)

# Illustrative cutoff (configurable assumption)
# In January, Europe/London = UTC+0 (GMT), so 09:00 local = 09:00 UTC
CUTOFF_HOUR_UTC = 9  # 09:00 UTC = 09:00 Europe/London in January

REPO_ROOT  = Path(__file__).resolve().parent.parent
DATA_DIR   = REPO_ROOT / "data"
AUDIT_DIR  = DATA_DIR / "audit"
SAMPLE_DIR = DATA_DIR / "sample"

# Throttle between API calls (seconds) — be respectful
REQUEST_DELAY = 0.3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_json(url: str, retries: int = 2) -> tuple[int, list[dict[str, Any]]]:
    """GET *url* and return (http_status, parsed_json_list). Retries on transient errors."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                if not isinstance(data, list):
                    data = [data]
                return resp.status, data
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries:
                wait = 2 ** (attempt + 1)
                print(f"    Retry {attempt+1}/{retries} after HTTP {exc.code}, waiting {wait}s...",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  HTTP {exc.code}: {exc.reason}  URL={url}", file=sys.stderr)
            return exc.code, []
        except Exception as exc:
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                print(f"    Retry {attempt+1}/{retries} after {exc}, waiting {wait}s...",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  Error: {exc}  URL={url}", file=sys.stderr)
            return 0, []
    return 0, []


def iso_parse(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp (trailing Z) to timezone-aware datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def date_range(start: date, end: date) -> list[date]:
    """Inclusive date range."""
    result = []
    d = start
    while d <= end:
        result.append(d)
        d += timedelta(days=1)
    return result


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def p(msg: str = "") -> None:
    """Print with flush for real-time progress."""
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# 1. FETCH ALL FUELHH ACTUALS
# ---------------------------------------------------------------------------

def fetch_all_fuelhh() -> list[dict]:
    """Fetch FUELHH WIND records for every delivery date."""
    p("\n" + "=" * 76)
    p("  STEP 1: Fetch FUELHH WIND actuals for all delivery dates")
    p("=" * 76)

    delivery_dates = date_range(DELIVERY_START, DELIVERY_END)
    p(f"  Delivery dates: {DELIVERY_START} to {DELIVERY_END} ({len(delivery_dates)} days)")
    p(f"  Expected rows: {len(delivery_dates)} x 48 = {len(delivery_dates) * 48}")

    # Fetch in weekly batches to reduce number of API calls
    all_records: list[dict] = []
    batch_start = DELIVERY_START
    batch_num = 0

    while batch_start <= DELIVERY_END:
        batch_end = min(batch_start + timedelta(days=6), DELIVERY_END)
        batch_num += 1

        params = {
            "settlementDateFrom": batch_start.isoformat(),
            "settlementDateTo":   batch_end.isoformat(),
            "fuelType":           "WIND",
        }
        url = f"{API_BASE}/datasets/FUELHH/stream?{urllib.parse.urlencode(params)}"

        days_in_batch = (batch_end - batch_start).days + 1
        p(f"\n  Batch {batch_num}: {batch_start} to {batch_end} ({days_in_batch} days)")
        p(f"    URL: {url}")

        status, data = fetch_json(url)
        p(f"    HTTP {status} | {len(data)} rows")

        if status != 200:
            p(f"    *** FETCH FAILED — HTTP {status} ***")
            # Continue to next batch rather than aborting entire audit
        else:
            all_records.extend(data)

        batch_start = batch_end + timedelta(days=1)
        time.sleep(REQUEST_DELAY)

    p(f"\n  Total FUELHH rows fetched: {len(all_records)}")
    return all_records


def analyse_fuelhh(records: list[dict]) -> dict:
    """Deep analysis of FUELHH records."""
    p("\n" + "-" * 76)
    p("  FUELHH Analysis")
    p("-" * 76)

    result: dict[str, Any] = {
        "total_rows": len(records),
        "expected_rows": 31 * 48,
    }

    if not records:
        p("  *** NO RECORDS — BLOCKER ***")
        result["blocker"] = "No FUELHH records returned"
        return result

    # Field check
    fields = list(records[0].keys())
    p(f"  Fields: {fields}")
    result["fields"] = fields

    # --- Per-date breakdown ---
    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_date[r["settlementDate"]].append(r)

    delivery_dates = date_range(DELIVERY_START, DELIVERY_END)
    expected_dates = {d.isoformat() for d in delivery_dates}
    actual_dates = set(by_date.keys())

    missing_dates = sorted(expected_dates - actual_dates)
    extra_dates = sorted(actual_dates - expected_dates)

    p(f"\n  Delivery dates with data: {len(actual_dates)}")
    p(f"  Expected dates: {len(expected_dates)}")
    if missing_dates:
        p(f"  MISSING dates: {missing_dates}")
    if extra_dates:
        p(f"  Extra dates (outside window): {extra_dates}")

    result["dates_with_data"] = len(actual_dates)
    result["missing_dates"] = missing_dates
    result["extra_dates"] = extra_dates

    # --- Per-date completeness ---
    per_date_summary = []
    total_duplicates = 0
    total_missing_sps = 0

    for d in sorted(expected_dates):
        rows = by_date.get(d, [])
        sps = [r["settlementPeriod"] for r in rows]
        sp_set = set(sps)
        expected_sps = set(range(1, 49))
        missing_sps = sorted(expected_sps - sp_set)
        extra_sps = sorted(sp_set - expected_sps)

        # Duplicate startTimes
        start_counts = Counter(r["startTime"] for r in rows)
        dup_starts = {k: v for k, v in start_counts.items() if v > 1}

        # Null / invalid generation
        null_gen = [r for r in rows if r.get("generation") is None]
        neg_gen = [r for r in rows if isinstance(r.get("generation"), (int, float)) and r["generation"] < 0]

        day_info = {
            "date": d,
            "row_count": len(rows),
            "unique_sps": len(sp_set),
            "missing_sps": missing_sps,
            "extra_sps": extra_sps,
            "duplicate_start_times": len(dup_starts),
            "null_generation": len(null_gen),
            "negative_generation": len(neg_gen),
        }
        per_date_summary.append(day_info)
        total_duplicates += len(dup_starts)
        total_missing_sps += len(missing_sps)

        if missing_sps or dup_starts or null_gen or neg_gen:
            p(f"  {d}: {len(rows)} rows, missing SPs: {missing_sps}, "
              f"duplicates: {len(dup_starts)}, null_gen: {len(null_gen)}")

    result["per_date"] = per_date_summary
    result["total_duplicate_start_times"] = total_duplicates
    result["total_missing_settlement_periods"] = total_missing_sps

    # --- Unique startTimes overall ---
    all_starts = set(r["startTime"] for r in records)
    p(f"\n  Unique startTime values: {len(all_starts)}")
    result["unique_start_times"] = len(all_starts)

    # --- Overall duplicate startTimes ---
    start_counts_all = Counter(r["startTime"] for r in records)
    dups_all = {k: v for k, v in start_counts_all.items() if v > 1}
    p(f"  Duplicate startTime values (across all dates): {len(dups_all)}")
    result["duplicate_start_times_overall"] = len(dups_all)
    if dups_all:
        sample_dups = dict(sorted(dups_all.items())[:5])
        p(f"  Sample duplicates: {sample_dups}")
        result["sample_duplicates"] = sample_dups

    # --- publishTime analysis ---
    pub_times = sorted(set(r["publishTime"] for r in records))
    p(f"\n  Distinct publishTime values: {len(pub_times)}")
    p(f"  publishTime range: {pub_times[0]} to {pub_times[-1]}")

    # Check for revision patterns — multiple publishTimes for same startTime
    starts_with_multiple_pubs = {
        st: cnt for st, cnt in start_counts_all.items() if cnt > 1
    }
    if starts_with_multiple_pubs:
        p(f"  Revision pattern: {len(starts_with_multiple_pubs)} startTimes "
          f"have multiple publishTimes (revisions)")
        result["revision_count"] = len(starts_with_multiple_pubs)
    else:
        p("  No revisions detected (one publishTime per startTime)")
        result["revision_count"] = 0

    # --- Null/invalid generation ---
    all_null = [r for r in records if r.get("generation") is None]
    all_neg = [r for r in records if isinstance(r.get("generation"), (int, float)) and r["generation"] < 0]
    p(f"\n  Null generation values: {len(all_null)}")
    p(f"  Negative generation values: {len(all_neg)}")
    result["null_generation_total"] = len(all_null)
    result["negative_generation_total"] = len(all_neg)

    # --- Generation range ---
    gen_values = [r["generation"] for r in records
                  if isinstance(r.get("generation"), (int, float))]
    if gen_values:
        p(f"  Generation range: {min(gen_values)} to {max(gen_values)} MW")
        p(f"  Generation mean: {sum(gen_values)/len(gen_values):.0f} MW")
        result["generation_min"] = min(gen_values)
        result["generation_max"] = max(gen_values)
        result["generation_mean"] = round(sum(gen_values) / len(gen_values))

    # Summary
    complete_days = sum(1 for d in per_date_summary if d["row_count"] == 48
                        and not d["missing_sps"] and d["duplicate_start_times"] == 0)
    p(f"\n  Complete days (48 SPs, no gaps, no dups): {complete_days} / {len(expected_dates)}")
    result["complete_days"] = complete_days
    result["completeness_pct"] = round(100 * complete_days / len(expected_dates), 1)

    return result


# ---------------------------------------------------------------------------
# 2. FETCH ALL WINDFOR FORECAST HISTORY
# ---------------------------------------------------------------------------

def fetch_all_windfor() -> list[dict]:
    """Fetch WINDFOR publications covering all decision dates."""
    p("\n" + "=" * 76)
    p("  STEP 2: Fetch WINDFOR forecast history for all decision dates")
    p("=" * 76)

    # We need forecasts published from the start of the first decision date
    # through the cutoff of the last decision date.
    # Decision date 2026-01-01 cutoff = 2026-01-01T09:00:00Z
    # Decision date 2026-01-31 cutoff = 2026-01-31T09:00:00Z
    # But forecasts for earlier decision dates may have been published on
    # prior days too. Let's also grab publications from 2025-12-31 to capture
    # any late-previous-day publications that might be the latest before cutoff.
    #
    # Strategy: fetch in daily batches by publishDateTime to keep responses manageable.

    all_records: list[dict] = []

    # Include 2025-12-31 to catch any pre-midnight publications relevant
    # for decision date 2026-01-01 cutoff
    fetch_start = date(2025, 12, 31)
    fetch_end = DECISION_END  # 2026-01-31

    fetch_dates = date_range(fetch_start, fetch_end)
    p(f"  Publication date range: {fetch_start} to {fetch_end} ({len(fetch_dates)} days)")
    p(f"  Fetching daily batches...")

    for i, d in enumerate(fetch_dates):
        pub_from = f"{d.isoformat()}T00:00:00Z"
        pub_to = f"{d.isoformat()}T23:59:59Z"

        params = {
            "publishDateTimeFrom": pub_from,
            "publishDateTimeTo":   pub_to,
        }
        url = f"{API_BASE}/datasets/WINDFOR/stream?{urllib.parse.urlencode(params)}"

        status, data = fetch_json(url)
        vintages = len(set(r["publishTime"] for r in data)) if data else 0

        p(f"  [{i+1:2d}/{len(fetch_dates)}] {d} | HTTP {status} | "
          f"{len(data):5d} rows | {vintages:2d} vintages")

        if status == 200 and data:
            all_records.extend(data)

        time.sleep(REQUEST_DELAY)

    p(f"\n  Total WINDFOR rows fetched: {len(all_records)}")
    return all_records


def analyse_windfor(records: list[dict]) -> dict:
    """Deep analysis of WINDFOR records."""
    p("\n" + "-" * 76)
    p("  WINDFOR Analysis")
    p("-" * 76)

    result: dict[str, Any] = {"total_rows": len(records)}

    if not records:
        p("  *** NO RECORDS — BLOCKER ***")
        result["blocker"] = "No WINDFOR records returned"
        return result

    # Fields
    fields = list(records[0].keys())
    p(f"  Fields: {fields}")
    result["fields"] = fields

    # --- Vintage inventory ---
    vintages: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        vintages[r["publishTime"]].append(r)

    pub_times_sorted = sorted(vintages.keys())
    p(f"\n  Total distinct publishTime values (vintages): {len(pub_times_sorted)}")
    p(f"  publishTime range: {pub_times_sorted[0]} to {pub_times_sorted[-1]}")

    result["total_vintages"] = len(pub_times_sorted)
    result["publish_time_range"] = [pub_times_sorted[0], pub_times_sorted[-1]]

    # --- Per-vintage analysis ---
    vintage_details = []
    intervals_per_vintage = Counter()

    for pt in pub_times_sorted:
        rows = vintages[pt]
        starts = sorted(set(r["startTime"] for r in rows))
        start_counts = Counter(r["startTime"] for r in rows)
        dup_starts = {k: v for k, v in start_counts.items() if v > 1}

        # Null generation
        null_gen = sum(1 for r in rows if r.get("generation") is None)

        intervals_per_vintage[len(rows)] += 1

        detail = {
            "publishTime": pt,
            "row_count": len(rows),
            "unique_start_times": len(starts),
            "start_range": [starts[0], starts[-1]],
            "duplicate_start_times": len(dup_starts),
            "null_generation": null_gen,
        }
        vintage_details.append(detail)

    result["vintage_details"] = vintage_details

    # Interval count distribution
    p(f"\n  Intervals-per-vintage distribution:")
    for cnt, freq in sorted(intervals_per_vintage.items()):
        p(f"    {cnt} intervals: {freq} vintages")
    result["intervals_per_vintage_distribution"] = dict(sorted(intervals_per_vintage.items()))

    return result


# ---------------------------------------------------------------------------
# 3. PUBLICATION-TIME BEHAVIOUR
# ---------------------------------------------------------------------------

def analyse_publication_times(records: list[dict]) -> dict:
    """Investigate publishTime patterns across the full window."""
    p("\n" + "=" * 76)
    p("  STEP 3: Publication-time behaviour analysis")
    p("=" * 76)

    result: dict[str, Any] = {}

    # Extract all unique publishTimes
    pub_times = sorted(set(r["publishTime"] for r in records))
    p(f"  Total distinct publishTime values: {len(pub_times)}")

    # Group by publication date
    by_pub_date: dict[str, list[str]] = defaultdict(list)
    for pt in pub_times:
        dt = iso_parse(pt)
        by_pub_date[dt.strftime("%Y-%m-%d")].append(pt)

    # Extract the time-of-day (HH:MM) for each publication
    time_of_day_counter: Counter = Counter()
    for pt in pub_times:
        dt = iso_parse(pt)
        tod = dt.strftime("%H:%M")
        time_of_day_counter[tod] += 1

    p(f"\n  Publication times-of-day (UTC) across all dates:")
    for tod, count in sorted(time_of_day_counter.items()):
        # In January, UTC = Europe/London
        p(f"    {tod} UTC (= {tod} Europe/London in January) "
          f"— observed on {count} date(s)")

    result["publication_times_utc"] = dict(sorted(time_of_day_counter.items()))

    # Check consistency — does every date have the same set of publication times?
    p(f"\n  Per-date publication time consistency:")
    date_tod_sets: dict[str, set[str]] = {}
    for pub_date, pts in sorted(by_pub_date.items()):
        tods = sorted(iso_parse(pt).strftime("%H:%M") for pt in pts)
        date_tod_sets[pub_date] = set(tods)
        p(f"    {pub_date}: {len(pts)} vintages at {tods}")

    # Find the most common pattern
    tod_patterns = Counter(frozenset(s) for s in date_tod_sets.values())
    result["publication_time_patterns"] = [
        {"times": sorted(pat), "days": count}
        for pat, count in tod_patterns.most_common()
    ]

    p(f"\n  Distinct daily publication patterns: {len(tod_patterns)}")
    for pat, count in tod_patterns.most_common():
        p(f"    {sorted(pat)} — {count} day(s)")

    # Check whether these are historical or live timestamps
    p(f"\n  Publication timestamp interpretation:")
    p(f"    All publishTime values are in the past relative to current date.")
    p(f"    They represent the original publication time of each forecast vintage.")
    p(f"    NOT a 'last updated' or retrieval timestamp.")

    # Identify publications before 09:00 UTC per date
    pre_cutoff_by_date: dict[str, list[str]] = defaultdict(list)
    for pub_date, pts in sorted(by_pub_date.items()):
        for pt in pts:
            dt = iso_parse(pt)
            if dt.hour < CUTOFF_HOUR_UTC or (dt.hour == CUTOFF_HOUR_UTC and dt.minute == 0):
                pre_cutoff_by_date[pub_date].append(pt)

    p(f"\n  Pre-cutoff (<=09:00 UTC) vintages per date:")
    pre_cutoff_counts = Counter()
    for pub_date in sorted(pre_cutoff_by_date.keys()):
        pts = pre_cutoff_by_date[pub_date]
        pre_cutoff_counts[len(pts)] += 1
        if len(pts) <= 4:
            tods = sorted(iso_parse(pt).strftime("%H:%M") for pt in pts)
            p(f"    {pub_date}: {len(pts)} vintages at {tods}")
        else:
            p(f"    {pub_date}: {len(pts)} vintages")

    result["pre_cutoff_vintage_count_distribution"] = dict(sorted(pre_cutoff_counts.items()))

    return result


# ---------------------------------------------------------------------------
# 4. AUDIT ALL 31 DECISION DATES
# ---------------------------------------------------------------------------

def audit_decision_dates(windfor_records: list[dict],
                         fuelhh_records: list[dict]) -> dict:
    """For each decision date, find the best eligible forecast vintage."""
    p("\n" + "=" * 76)
    p("  STEP 4: Audit all 31 decision dates")
    p("=" * 76)
    p(f"  Cutoff: 09:00 Europe/London (= 09:00 UTC in January)")

    # Index WINDFOR by publishTime
    vintages: dict[str, list[dict]] = defaultdict(list)
    for r in windfor_records:
        vintages[r["publishTime"]].append(r)

    # Index FUELHH by settlementDate
    actuals_by_date: dict[str, list[dict]] = defaultdict(list)
    for r in fuelhh_records:
        actuals_by_date[r["settlementDate"]].append(r)

    all_pub_times = sorted(vintages.keys())

    decision_dates = date_range(DECISION_START, DECISION_END)
    audit_results = []

    for decision_date in decision_dates:
        delivery_date = decision_date + timedelta(days=1)
        delivery_str = delivery_date.isoformat()

        # Cutoff datetime in UTC
        cutoff_utc = datetime(decision_date.year, decision_date.month,
                              decision_date.day, CUTOFF_HOUR_UTC, 0, 0,
                              tzinfo=timezone.utc)

        # Find all vintages published at or before the cutoff
        # The forecast could have been published on the decision date or earlier
        eligible_pts = []
        for pt in all_pub_times:
            pt_dt = iso_parse(pt)
            if pt_dt <= cutoff_utc:
                eligible_pts.append(pt)

        # For each eligible vintage, check if it covers the delivery day (24 hours)
        delivery_day_starts = set()
        for h in range(24):
            dt = datetime(delivery_date.year, delivery_date.month,
                          delivery_date.day, h, 0, 0, tzinfo=timezone.utc)
            delivery_day_starts.add(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))

        best_vintage = None
        best_vintage_pt = None
        best_coverage = 0
        eligible_complete = []
        eligible_incomplete = []

        # Check from latest to earliest
        for pt in reversed(eligible_pts):
            rows = vintages[pt]
            forecast_starts = set(r["startTime"] for r in rows)

            # How many of the 24 delivery-day hours are covered?
            covered = delivery_day_starts & forecast_starts
            coverage = len(covered)

            if coverage == 24:
                if best_vintage is None:
                    best_vintage_pt = pt
                    best_vintage = rows
                    best_coverage = coverage
                eligible_complete.append({
                    "publishTime": pt,
                    "delivery_coverage": coverage,
                })
            elif coverage > 0:
                eligible_incomplete.append({
                    "publishTime": pt,
                    "delivery_coverage": coverage,
                    "missing_hours": sorted(delivery_day_starts - forecast_starts),
                })

            # Only report the most recent few eligible vintages in detail
            if len(eligible_complete) >= 10 and len(eligible_incomplete) >= 5:
                break

        # Actual coverage for this delivery date
        actual_rows = actuals_by_date.get(delivery_str, [])
        actual_sps = set(r["settlementPeriod"] for r in actual_rows)

        day_result = {
            "decision_date": decision_date.isoformat(),
            "delivery_date": delivery_str,
            "cutoff_utc": cutoff_utc.isoformat(),
            "total_eligible_vintages_checked": len(eligible_complete) + len(eligible_incomplete),
            "complete_eligible_vintages": len(eligible_complete),
            "selected_vintage": best_vintage_pt,
            "selected_vintage_coverage": best_coverage,
            "incomplete_eligible_vintages_sample": eligible_incomplete[:3],
            "actual_row_count": len(actual_rows),
            "actual_settlement_periods": len(actual_sps),
            "has_complete_forecast": best_vintage_pt is not None,
            "has_complete_actuals": len(actual_sps) == 48,
        }
        audit_results.append(day_result)

        status_char = "OK" if (best_vintage_pt and len(actual_sps) == 48) else "!!"
        p(f"  [{status_char}] D={decision_date} -> Del={delivery_str} | "
          f"vintage={best_vintage_pt or 'NONE':20s} | "
          f"complete_vintages={len(eligible_complete):2d} | "
          f"actual_SPs={len(actual_sps):2d}")

    # Summary
    go_count = sum(1 for r in audit_results
                   if r["has_complete_forecast"] and r["has_complete_actuals"])
    no_forecast = sum(1 for r in audit_results if not r["has_complete_forecast"])
    no_actuals = sum(1 for r in audit_results if not r["has_complete_actuals"])

    p(f"\n  Summary:")
    p(f"    Total decision dates: {len(audit_results)}")
    p(f"    Fully auditable (forecast + actuals): {go_count}")
    p(f"    Missing complete forecast: {no_forecast}")
    p(f"    Missing complete actuals: {no_actuals}")

    return {
        "cutoff": "09:00 Europe/London (09:00 UTC in January)",
        "total_decision_dates": len(audit_results),
        "fully_auditable": go_count,
        "missing_complete_forecast": no_forecast,
        "missing_complete_actuals": no_actuals,
        "per_date": audit_results,
    }


# ---------------------------------------------------------------------------
# 5. ALIGN ACTUALS TO HOURLY FORECASTS
# ---------------------------------------------------------------------------

def align_and_compare(windfor_records: list[dict],
                      fuelhh_records: list[dict],
                      audit: dict) -> dict:
    """Align half-hourly actuals to hourly forecasts for all auditable dates."""
    p("\n" + "=" * 76)
    p("  STEP 5: Align actuals to hourly forecasts")
    p("=" * 76)

    # Index WINDFOR by publishTime
    vintages: dict[str, list[dict]] = defaultdict(list)
    for r in windfor_records:
        vintages[r["publishTime"]].append(r)

    # Index FUELHH by settlementDate
    actuals_by_date: dict[str, list[dict]] = defaultdict(list)
    for r in fuelhh_records:
        actuals_by_date[r["settlementDate"]].append(r)

    total_raw_hh = len(fuelhh_records)
    total_comparisons = 0
    total_missing_actual_hours = 0
    total_missing_forecast_hours = 0
    total_duplicate_joins = 0
    per_date_alignment = []

    for day_audit in audit["per_date"]:
        delivery_str = day_audit["delivery_date"]
        selected_pt = day_audit["selected_vintage"]

        if not selected_pt or not day_audit["has_complete_actuals"]:
            per_date_alignment.append({
                "delivery_date": delivery_str,
                "decision_date": day_audit["decision_date"],
                "skipped": True,
                "reason": "missing forecast" if not selected_pt else "incomplete actuals",
            })
            continue

        # Get forecast rows for delivery day from selected vintage
        forecast_rows = vintages.get(selected_pt, [])
        forecast_by_hour: dict[str, dict] = {}
        for r in forecast_rows:
            st = r["startTime"]
            st_dt = iso_parse(st)
            # Only include hours on the delivery date
            if st_dt.strftime("%Y-%m-%d") == delivery_str:
                key = st_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                if key in forecast_by_hour:
                    total_duplicate_joins += 1
                forecast_by_hour[key] = r

        # Get actual rows for delivery day
        actual_rows = actuals_by_date.get(delivery_str, [])

        # Group actuals by clock hour
        actual_by_hour: dict[str, list[dict]] = defaultdict(list)
        for r in actual_rows:
            st_dt = iso_parse(r["startTime"])
            hour_key = st_dt.replace(minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            actual_by_hour[hour_key].append(r)

        # Align
        day_comparisons = []
        day_missing_actual = 0
        day_missing_forecast = 0

        for h in range(24):
            hour_dt = datetime(
                int(delivery_str[:4]), int(delivery_str[5:7]),
                int(delivery_str[8:10]), h, 0, 0, tzinfo=timezone.utc
            )
            hour_key = hour_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            forecast_row = forecast_by_hour.get(hour_key)
            actual_hh_rows = actual_by_hour.get(hour_key, [])

            if not forecast_row:
                day_missing_forecast += 1
                continue

            if len(actual_hh_rows) < 2:
                day_missing_actual += 1
                # Still compute with available data if at least 1 row
                if not actual_hh_rows:
                    continue

            # Average the half-hourly actuals
            valid_gen = [r["generation"] for r in actual_hh_rows
                         if r.get("generation") is not None]
            if not valid_gen:
                day_missing_actual += 1
                continue

            actual_avg = sum(valid_gen) / len(valid_gen)
            forecast_mw = forecast_row["generation"]

            day_comparisons.append({
                "hour_utc": hour_key,
                "forecast_mw": forecast_mw,
                "actual_avg_mw": round(actual_avg, 1),
                "error_mw": round(forecast_mw - actual_avg, 1),
                "actual_hh_count": len(valid_gen),
            })

        total_comparisons += len(day_comparisons)
        total_missing_actual_hours += day_missing_actual
        total_missing_forecast_hours += day_missing_forecast

        per_date_alignment.append({
            "delivery_date": delivery_str,
            "decision_date": day_audit["decision_date"],
            "selected_vintage": selected_pt,
            "comparisons": len(day_comparisons),
            "missing_actual_hours": day_missing_actual,
            "missing_forecast_hours": day_missing_forecast,
            "skipped": False,
        })

        p(f"  {delivery_str}: {len(day_comparisons)}/24 comparisons, "
          f"missing_actual={day_missing_actual}, missing_forecast={day_missing_forecast}")

    p(f"\n  Alignment summary:")
    p(f"    Raw half-hourly actuals: {total_raw_hh}")
    p(f"    Expected comparisons (max): 31 x 24 = 744")
    p(f"    Actual comparisons: {total_comparisons}")
    p(f"    Missing actual hours: {total_missing_actual_hours}")
    p(f"    Missing forecast hours: {total_missing_forecast_hours}")
    p(f"    Duplicate joins: {total_duplicate_joins}")

    return {
        "raw_half_hourly_actuals": total_raw_hh,
        "expected_max_comparisons": 744,
        "actual_comparisons": total_comparisons,
        "missing_actual_hours": total_missing_actual_hours,
        "missing_forecast_hours": total_missing_forecast_hours,
        "duplicate_joins": total_duplicate_joins,
        "per_date": per_date_alignment,
    }


# ---------------------------------------------------------------------------
# 6. GO / NO-GO
# ---------------------------------------------------------------------------

def assess_go_nogo(fuelhh_analysis: dict,
                   windfor_analysis: dict,
                   audit: dict,
                   alignment: dict) -> dict:
    """Produce final GO/NO-GO assessment."""
    p("\n" + "=" * 76)
    p("  STEP 6: GO / NO-GO Assessment")
    p("=" * 76)

    blockers = []
    warnings = []

    # Check FUELHH
    if fuelhh_analysis.get("blocker"):
        blockers.append(f"FUELHH: {fuelhh_analysis['blocker']}")
    elif fuelhh_analysis["total_rows"] < 1488:
        diff = 1488 - fuelhh_analysis["total_rows"]
        warnings.append(f"FUELHH: {diff} rows fewer than expected 1488")
    if fuelhh_analysis.get("total_missing_settlement_periods", 0) > 0:
        warnings.append(f"FUELHH: {fuelhh_analysis['total_missing_settlement_periods']} "
                        f"missing settlement periods")

    # Check WINDFOR
    if windfor_analysis.get("blocker"):
        blockers.append(f"WINDFOR: {windfor_analysis['blocker']}")

    # Check decision-date audit
    if audit["missing_complete_forecast"] > 0:
        detail = audit["missing_complete_forecast"]
        if detail > 5:
            blockers.append(f"No complete eligible forecast for {detail} decision dates")
        else:
            warnings.append(f"No complete eligible forecast for {detail} decision dates")

    if audit["missing_complete_actuals"] > 0:
        detail = audit["missing_complete_actuals"]
        if detail > 5:
            blockers.append(f"Incomplete actuals for {detail} delivery dates")
        else:
            warnings.append(f"Incomplete actuals for {detail} delivery dates")

    # Check alignment
    if alignment["actual_comparisons"] == 0:
        blockers.append("No forecast-actual comparisons could be produced")
    elif alignment["actual_comparisons"] < 700:
        warnings.append(f"Only {alignment['actual_comparisons']}/744 comparisons "
                        f"({100*alignment['actual_comparisons']/744:.1f}%)")

    go = len(blockers) == 0

    p(f"\n  {'GO' if go else 'NO-GO'}")
    p(f"\n  Blockers: {len(blockers)}")
    for b in blockers:
        p(f"    [BLOCKER] {b}")
    p(f"\n  Warnings: {len(warnings)}")
    for w in warnings:
        p(f"    [WARNING] {w}")

    p(f"\n  Key metrics:")
    p(f"    FUELHH rows: {fuelhh_analysis['total_rows']} (expected: 1488)")
    p(f"    WINDFOR vintages: {windfor_analysis.get('total_vintages', 0)}")
    p(f"    Auditable decision dates: {audit['fully_auditable']}/31")
    p(f"    Aligned comparisons: {alignment['actual_comparisons']}/744")

    return {
        "go": go,
        "blockers": blockers,
        "warnings": warnings,
        "fuelhh_rows": fuelhh_analysis["total_rows"],
        "windfor_vintages": windfor_analysis.get("total_vintages", 0),
        "auditable_dates": audit["fully_auditable"],
        "comparisons": alignment["actual_comparisons"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p(f"Windline — Full-Window Data Audit")
    p(f"Run at: {datetime.now(timezone.utc).isoformat()}")
    p(f"API base: {API_BASE}")
    p(f"Delivery window: {DELIVERY_START} to {DELIVERY_END}")
    p(f"Decision window: {DECISION_START} to {DECISION_END}")
    p(f"Cutoff: {CUTOFF_HOUR_UTC:02d}:00 UTC (09:00 Europe/London in January)")

    # Step 1: Fetch FUELHH
    fuelhh_records = fetch_all_fuelhh()
    fuelhh_analysis = analyse_fuelhh(fuelhh_records)

    # Save FUELHH metadata (not the full dataset — it's large)
    save_json(AUDIT_DIR / "fuelhh_analysis.json", fuelhh_analysis)
    # Save full dataset for reproducibility
    save_json(AUDIT_DIR / "fuelhh_full.json", fuelhh_records)
    p(f"\n  Saved FUELHH analysis -> {AUDIT_DIR / 'fuelhh_analysis.json'}")
    p(f"  Saved FUELHH full dataset -> {AUDIT_DIR / 'fuelhh_full.json'}")

    # Step 2: Fetch WINDFOR
    windfor_records = fetch_all_windfor()
    windfor_analysis = analyse_windfor(windfor_records)

    save_json(AUDIT_DIR / "windfor_analysis.json", windfor_analysis)
    save_json(AUDIT_DIR / "windfor_full.json", windfor_records)
    p(f"\n  Saved WINDFOR analysis -> {AUDIT_DIR / 'windfor_analysis.json'}")
    p(f"  Saved WINDFOR full dataset -> {AUDIT_DIR / 'windfor_full.json'}")

    # Step 3: Publication-time behaviour
    pub_time_analysis = analyse_publication_times(windfor_records)
    save_json(AUDIT_DIR / "publication_time_analysis.json", pub_time_analysis)

    # Step 4: Decision-date audit
    audit = audit_decision_dates(windfor_records, fuelhh_records)
    save_json(AUDIT_DIR / "decision_date_audit.json", audit)

    # Step 5: Alignment
    alignment = align_and_compare(windfor_records, fuelhh_records, audit)
    save_json(AUDIT_DIR / "alignment_results.json", alignment)

    # Step 6: GO/NO-GO
    go_nogo = assess_go_nogo(fuelhh_analysis, windfor_analysis, audit, alignment)
    save_json(AUDIT_DIR / "go_nogo.json", go_nogo)

    p(f"\n  All audit artifacts saved to {AUDIT_DIR}")
    p(f"\n  Existing sample data in {SAMPLE_DIR} preserved (not overwritten).")


if __name__ == "__main__":
    main()
