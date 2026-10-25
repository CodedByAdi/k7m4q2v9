"""FastAPI integration and endpoint tests using TestClient."""

import csv
import json
import io
from fastapi.testclient import TestClient
import pytest

from backend.app.config import AUDIT_DIR
from backend.app.main import app

client = TestClient(app)


class TestEndpointsSmokeAndContracts:
    """Smoke tests and contract verification for all API endpoints."""

    def test_health_endpoint(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["app_name"] == "Windline"
        assert "version" in data
        assert "timestamp_utc" in data

    def test_metadata_endpoint(self):
        resp = client.get("/api/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project"] == "Windline"
        assert data["data_provider"] == "Elexon Insights Solution (BMRS)"
        assert data["date_windows"]["total_decision_days"] == 31
        assert data["date_windows"]["total_delivery_days"] == 31
        assert "mae" in data["metrics_definitions"]
        assert "wape" in data["metrics_definitions"]
        assert "source_files" in data["provenance"]

    def test_overview_reproduces_31_days_and_744_comparisons(self):
        """Default analysis reproduces 31 decision days and 744 hourly comparisons."""
        resp = client.get("/api/overview?cutoff=09:00")
        assert resp.status_code == 200
        data = resp.json()

        assert data["cutoff_local"] == "09:00"
        assert data["total_delivery_days"] == 31
        assert data["auditable_days"] == 31

        overall = data["overall_metrics"]
        assert overall["expected_intervals"] == 744
        assert overall["matched_intervals"] == 744
        assert overall["omitted_intervals"] == 0
        assert overall["coverage"] == 1.0

        # Numeric metrics must be populated and realistic
        assert overall["mae"] is not None and overall["mae"] > 0
        assert overall["rmse"] is not None and overall["rmse"] > 0
        assert overall["bias"] is not None
        assert overall["wape"] is not None and overall["wape"] > 0
        # Assert convention: WAPE is returned in percentage points (18.07%), not decimal ratio (0.1807) or double-multiplied (1807.0%)
        assert 15.0 <= overall["wape"] <= 25.0
        assert overall["wape"] == 18.07

        # 31 daily summaries
        assert len(data["daily_summaries"]) == 31
        first_day = data["daily_summaries"][0]
        assert first_day["delivery_date"] == "2026-01-02"
        assert first_day["decision_date"] == "2026-01-01"
        assert first_day["status"] == "complete"
        assert first_day["selected_publish_time"] == "2026-01-01T07:30:00Z"
        assert first_day["expected_intervals"] == 24
        assert first_day["observed_intervals"] == 24
        assert first_day["coverage"] == 1.0

        last_day = data["daily_summaries"][-1]
        assert last_day["delivery_date"] == "2026-02-01"
        assert last_day["decision_date"] == "2026-01-31"
        assert last_day["status"] == "complete"
        assert last_day["selected_publish_time"] == "2026-01-31T07:30:00Z"

    def test_wape_response_convention_is_percentage_points(self):
        """Ensure WAPE is returned in percentage points (e.g. 18.07 for 18.07%), never 0.1807 or 1807."""
        resp = client.get("/api/overview?cutoff=09:00")
        assert resp.status_code == 200
        wape = resp.json()["overall_metrics"]["wape"]
        assert wape is not None
        assert 1.0 < wape < 100.0, f"WAPE must be in percentage points, got {wape}"
        assert wape == 18.07

    def test_deliveries_list_endpoint(self):
        resp = client.get("/api/deliveries?cutoff=09:00")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cutoff_local"] == "09:00"
        assert data["total_days"] == 31
        assert len(data["deliveries"]) == 31

    def test_delivery_detail_endpoint(self):
        resp = client.get("/api/deliveries/2026-01-02?cutoff=09:00")
        assert resp.status_code == 200
        data = resp.json()

        assert data["delivery_date"] == "2026-01-02"
        assert data["decision_date"] == "2026-01-01"
        assert data["cutoff_local"] == "09:00"
        assert data["status"] == "complete"
        assert data["selected_vintage"]["publish_time"] == "2026-01-01T07:30:00Z"
        assert data["selected_vintage"]["is_complete"] is True
        assert data["latest_complete_vintage"]["publish_time"] == "2026-01-01T07:30:00Z"

        assert len(data["intervals"]) == 24
        assert len(data["missing_intervals"]) == 0

        # Check first hour structure
        h0 = data["intervals"][0]
        assert h0["startTime"] == "2026-01-02T00:00:00Z"
        assert h0["forecast_mw"] is not None
        assert h0["actual_mw"] is not None
        assert h0["signed_error_mw"] is not None
        assert h0["absolute_error_mw"] is not None
        assert h0["actual_half_hour_count"] == 2

    def test_delivery_vintages_audit_endpoint(self):
        resp = client.get("/api/deliveries/2026-01-02/vintages?cutoff=09:00")
        assert resp.status_code == 200
        data = resp.json()

        assert data["delivery_date"] == "2026-01-02"
        assert data["selected_latest_vintage"] == "2026-01-01T07:30:00Z"
        assert data["latest_complete_vintage"] == "2026-01-01T07:30:00Z"

        vintages = data["eligible_vintages"]
        assert len(vintages) >= 3

        # Exactly 3 morning vintages published before 09:00 on 2026-01-01
        morning_pts = [v["publish_time"] for v in vintages if v["publish_time"].startswith("2026-01-01")]
        assert morning_pts == ["2026-01-01T07:30:00Z", "2026-01-01T04:30:00Z", "2026-01-01T02:30:00Z"]

    def test_export_csv_endpoint(self):
        resp = client.get("/api/export.csv?cutoff=09:00")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment; filename=" in resp.headers["content-disposition"]

        reader = list(csv.reader(io.StringIO(resp.text)))
        headers = reader[0]
        expected_headers = [
            "deliveryDate",
            "decisionDate",
            "startTime",
            "forecast",
            "actual",
            "signedError",
            "absoluteError",
            "publishTime",
            "cutoff",
        ]
        assert headers == expected_headers

        data_rows = reader[1:]
        # Exactly 744 data rows (31 days * 24 hours)
        assert len(data_rows) == 744

        # Verify row 1
        r0 = data_rows[0]
        assert r0[0] == "2026-01-02"
        assert r0[1] == "2026-01-01"
        assert r0[2] == "2026-01-02T00:00:00Z"
        assert float(r0[3]) > 0  # forecast
        assert float(r0[4]) > 0  # actual
        assert r0[7] == "2026-01-01T07:30:00Z"  # publishTime


class TestErrorHandlingAndValidation:
    """Error handling, input validation, and JSON numerical hygiene tests."""

    def test_invalid_cutoff_input_returns_400(self):
        """Invalid cutoff input returns HTTP 400."""
        # Bad formats
        for bad_cutoff in ["99:99", "09:60", "25:00", "9:00", "abc", ""]:
            resp = client.get(f"/api/overview?cutoff={bad_cutoff}")
            assert resp.status_code == 400

            resp2 = client.get(f"/api/deliveries?cutoff={bad_cutoff}")
            assert resp2.status_code == 400

            resp3 = client.get(f"/api/deliveries/2026-01-02?cutoff={bad_cutoff}")
            assert resp3.status_code == 400

    def test_invalid_delivery_date_format_returns_400(self):
        """Invalid delivery date format returns HTTP 400."""
        for bad_date in ["not-a-date", "02-01-2026", "2026-1-2", "2026-99-99", "invalid-date"]:
            resp = client.get(f"/api/deliveries/{bad_date}")
            assert resp.status_code == 400


    def test_out_of_window_delivery_date_returns_400(self):
        """Out-of-window delivery dates return a clear client error."""
        # Valid window is 2026-01-02 to 2026-02-01
        for out_date in ["2026-01-01", "2025-12-31", "2026-02-02", "2026-03-01"]:
            resp = client.get(f"/api/deliveries/{out_date}")
            assert resp.status_code == 400
            assert "outside the January delivery window" in resp.json()["detail"]

    def test_no_nan_or_infinity_in_json_responses(self):
        """API responses contain no NaN or Infinity JSON values."""
        endpoints = [
            "/api/health",
            "/api/metadata",
            "/api/overview?cutoff=09:00",
            "/api/deliveries?cutoff=09:00",
            "/api/deliveries/2026-01-02?cutoff=09:00",
            "/api/deliveries/2026-02-01?cutoff=09:00",
            "/api/deliveries/2026-01-02/vintages?cutoff=09:00",
        ]

        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 200
            raw_text = resp.text
            # Strict JSON standard does not permit NaN, Infinity, -Infinity
            assert "NaN" not in raw_text
            assert "Infinity" not in raw_text
            assert "-Infinity" not in raw_text

            # Parse with strict python json parser to ensure standard compliance
            data = json.loads(raw_text)
            assert isinstance(data, dict)


class TestIndependentSnapshotVerification:
    """Verify that API outputs match independent calculations directly from raw JSON files."""

    def test_independent_snapshot_verification_for_day_1(self):
        """Verify delivery day 2026-01-02 against raw JSON files."""
        # 1. Read raw FUELHH
        with open(AUDIT_DIR / "fuelhh_full.json", "r", encoding="utf-8") as f:
            fuelhh_raw = json.load(f)

        day_actuals = [
            r for r in fuelhh_raw
            if r["settlementDate"] == "2026-01-02" and r["fuelType"] == "WIND"
        ]
        assert len(day_actuals) == 48

        # Calculate actual average for hour 00:00:00Z
        sp1 = next(r for r in day_actuals if r["settlementPeriod"] == 1)["generation"]
        sp2 = next(r for r in day_actuals if r["settlementPeriod"] == 2)["generation"]
        expected_h0_actual = (sp1 + sp2) / 2.0

        # 2. Read raw WINDFOR
        with open(AUDIT_DIR / "windfor_full.json", "r", encoding="utf-8") as f:
            windfor_raw = json.load(f)

        vintage_0730 = [
            r for r in windfor_raw
            if r["publishTime"] == "2026-01-01T07:30:00Z"
        ]
        assert len(vintage_0730) == 73

        expected_h0_forecast = next(
            r for r in vintage_0730 if r["startTime"] == "2026-01-02T00:00:00Z"
        )["generation"]

        # 3. Query API
        resp = client.get("/api/deliveries/2026-01-02?cutoff=09:00")
        assert resp.status_code == 200
        data = resp.json()

        h0 = data["intervals"][0]
        assert h0["startTime"] == "2026-01-02T00:00:00Z"
        assert h0["actual_mw"] == round(expected_h0_actual, 1)
        assert h0["forecast_mw"] == round(expected_h0_forecast, 1)
        assert h0["signed_error_mw"] == round(expected_h0_forecast - expected_h0_actual, 1)
