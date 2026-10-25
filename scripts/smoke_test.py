#!/usr/bin/env python3
"""Acceptance checks & smoke test script for Windline Phase 1."""

import json
import math
import subprocess
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

## UTF-8 stdout on Windows
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

# Fix sandbox permission traversal
import os
_orig_stat = os.stat
def _sandboxed_stat(path, *args, **kwargs):
    try:
        return _orig_stat(path, *args, **kwargs)
    except PermissionError:
        p_str = str(path).rstrip("\\/").upper()
        if len(p_str) <= 2 and (len(p_str) == 0 or p_str.endswith(":")):
            return _orig_stat(".", *args, **kwargs)
        raise
os.stat = _sandboxed_stat

from fastapi.testclient import TestClient

from backend.app.config import AUDIT_DIR
from backend.app.main import app

client = TestClient(app)


def run_checks():
    print("=" * 76)
    print("WINDLINE PHASE 1 -- ACCEPTANCE CHECKS")
    print("=" * 76)

    # 1. Compilation check
    print("\n[1/4] Running Python py_compile check...")
    py_files = [
        "backend/app/config.py",
        "backend/app/timestamps.py",
        "backend/app/metrics.py",
        "backend/app/models.py",
        "backend/app/loader.py",
        "backend/app/engine.py",
        "backend/app/routes.py",
        "backend/app/main.py",
        "backend/tests/test_domain_and_metrics.py",
        "backend/tests/test_forecast_selection.py",
        "backend/tests/test_api_endpoints.py",
    ]
    import py_compile
    for f in py_files:
        py_compile.compile(f, doraise=True)
    print(f"  [OK] All {len(py_files)} Python source and test files compiled cleanly.")

    # 2. Pytest test suite
    print("\n[2/4] Running pytest suite via pytest.main()...")
    import pytest
    code = pytest.main(["backend/tests", "-v", "--tb=short"])
    if code != 0:
        print(f"  [FAIL] Pytest failed with exit code {code}")
        sys.exit(code)
    print("  [OK] All pytest tests passed successfully.")

    # 3. FastAPI TestClient Smoke Test for all endpoints
    print("\n[3/4] Running FastAPI TestClient smoke tests...")
    endpoints = [
        ("/api/health", 200),
        ("/api/metadata", 200),
        ("/api/overview?cutoff=09:00", 200),
        ("/api/deliveries?cutoff=09:00", 200),
        ("/api/deliveries/2026-01-02?cutoff=09:00", 200),
        ("/api/deliveries/2026-02-01?cutoff=09:00", 200),
        ("/api/deliveries/2026-01-02/vintages?cutoff=09:00", 200),
        ("/api/export.csv?cutoff=09:00", 200),
        # Bad cutoff error
        ("/api/overview?cutoff=99:99", 400),
        # Bad delivery date error
        ("/api/deliveries/bad-date", 400),
        # Out-of-window delivery date error
        ("/api/deliveries/2026-03-01", 400),
    ]
    for url, expected_status in endpoints:
        resp = client.get(url)
        assert resp.status_code == expected_status, f"Expected {expected_status} for {url}, got {resp.status_code}: {resp.text}"
        print(f"  [OK] GET {url:48s} -> HTTP {resp.status_code}")

    # 4. Independent Snapshot Verification
    print("\n[4/4] Independent verification against raw JSON snapshots...")
    with open(AUDIT_DIR / "fuelhh_full.json", "r", encoding="utf-8") as f:
        fuelhh_raw = json.load(f)
    with open(AUDIT_DIR / "windfor_full.json", "r", encoding="utf-8") as f:
        windfor_raw = json.load(f)

    # Independent check for delivery date 2026-01-02, hour 00:00:00Z
    sp1 = next(r for r in fuelhh_raw if r["settlementDate"] == "2026-01-02" and r["settlementPeriod"] == 1)["generation"]
    sp2 = next(r for r in fuelhh_raw if r["settlementDate"] == "2026-01-02" and r["settlementPeriod"] == 2)["generation"]
    manual_actual_00 = (sp1 + sp2) / 2.0

    manual_forecast_00 = next(
        r for r in windfor_raw
        if r["publishTime"] == "2026-01-01T07:30:00Z" and r["startTime"] == "2026-01-02T00:00:00Z"
    )["generation"]

    manual_signed_error_00 = manual_forecast_00 - manual_actual_00
    manual_abs_error_00 = abs(manual_signed_error_00)

    # Compare with API response
    api_resp = client.get("/api/deliveries/2026-01-02?cutoff=09:00").json()
    api_h0 = api_resp["intervals"][0]

    assert api_h0["startTime"] == "2026-01-02T00:00:00Z"
    assert api_h0["actual_mw"] == round(manual_actual_00, 1)
    assert api_h0["forecast_mw"] == round(manual_forecast_00, 1)
    assert api_h0["signed_error_mw"] == round(manual_signed_error_00, 1)
    assert api_h0["absolute_error_mw"] == round(manual_abs_error_00, 1)

    print(f"  [OK] 2026-01-02 00:00:00Z Actual MW   : Raw Snapshot = {manual_actual_00:.1f} | API = {api_h0['actual_mw']:.1f}")
    print(f"  [OK] 2026-01-02 00:00:00Z Forecast MW : Raw Snapshot = {manual_forecast_00:.1f} | API = {api_h0['forecast_mw']:.1f}")
    print(f"  [OK] 2026-01-02 00:00:00Z Signed Err  : Raw Snapshot = {manual_signed_error_00:.1f} | API = {api_h0['signed_error_mw']:.1f}")

    # Check overview totals
    overview = client.get("/api/overview?cutoff=09:00").json()
    metrics = overview["overall_metrics"]
    print(f"\n  Window Overview Metrics (31 days, 744 intervals):")
    print(f"    * Expected Intervals: {metrics['expected_intervals']}")
    print(f"    * Matched Intervals : {metrics['matched_intervals']}")
    print(f"    * Coverage          : {metrics['coverage'] * 100:.1f}%")
    print(f"    * MAE               : {metrics['mae']} MW")
    print(f"    * RMSE              : {metrics['rmse']} MW")
    print(f"    * Signed Bias       : {metrics['bias']} MW ({'Overforecast' if metrics['bias'] > 0 else 'Underforecast'})")
    print(f"    * WAPE              : {metrics['wape']}%")


    print("\n" + "=" * 76)
    print("ALL ACCEPTANCE CHECKS PASSED SUCCESSFULLY")
    print("=" * 76)


if __name__ == "__main__":
    run_checks()
