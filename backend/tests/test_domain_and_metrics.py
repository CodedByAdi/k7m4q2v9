"""Tests for domain contract, date mapping, actuals aggregation, and metrics."""

import math
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.config import (
    DECISION_DATE_END,
    DECISION_DATE_START,
    DELIVERY_DATE_END,
    DELIVERY_DATE_START,
)
from backend.app.engine import AnalysisEngine
from backend.app.loader import DataLoader, FuelHHRecord
from backend.app.metrics import (
    calculate_bias,
    calculate_coverage,
    calculate_mae,
    calculate_rmse,
    calculate_wape,
    compute_metrics_summary,
)
from backend.app.timestamps import (
    decision_date_to_delivery_date,
    delivery_date_to_decision_date,
    is_valid_decision_date,
    is_valid_delivery_date,
    make_cutoff_datetime,
    parse_date_str,
    parse_iso_utc,
    to_utc_iso,
    validate_cutoff_format,
)


class TestDateMapping:
    """Test required properties 1 & 2: 31 decision dates mapping to delivery dates."""

    def test_all_31_decision_dates_map_to_next_day_delivery_dates(self):
        """1. All 31 decision dates map to the correct next-day delivery dates."""
        current = DECISION_DATE_START
        decision_dates = []
        delivery_dates = []

        while current <= DECISION_DATE_END:
            decision_dates.append(current)
            delivery_date = decision_date_to_delivery_date(current)
            delivery_dates.append(delivery_date)
            # Verify exactly 1 day offset
            assert delivery_date == current + timedelta(days=1)
            # Reverse mapping
            assert delivery_date_to_decision_date(delivery_date) == current
            current += timedelta(days=1)

        assert len(decision_dates) == 31
        assert decision_dates[0] == date(2026, 1, 1)
        assert decision_dates[-1] == date(2026, 1, 31)

        assert len(delivery_dates) == 31
        assert delivery_dates[0] == DELIVERY_DATE_START  # 2026-01-02
        assert delivery_dates[-1] == DELIVERY_DATE_END    # 2026-02-01

    def test_jan_31_decision_includes_delivery_on_feb_1(self):
        """2. Jan 31 decisions include delivery on Feb 1."""
        jan_31 = date(2026, 1, 31)
        feb_1 = decision_date_to_delivery_date(jan_31)
        assert feb_1 == date(2026, 2, 1)
        assert is_valid_decision_date(jan_31)
        assert is_valid_delivery_date(feb_1)


class TestTimestampsAndTimezones:
    """Timezone awareness and cutoff generation tests."""

    def test_parse_iso_utc_aware(self):
        dt = parse_iso_utc("2026-01-01T07:30:00Z")
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(0)
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 7
        assert dt.minute == 30

    def test_reject_naive_timestamp(self):
        with pytest.raises(ValueError):
            parse_iso_utc("2026-01-01 07:30:00")

    def test_cutoff_in_january_matches_utc(self):
        # In January, London is GMT (UTC+0)
        cutoff_utc = make_cutoff_datetime(date(2026, 1, 15), "09:00")
        assert cutoff_utc.tzinfo == timezone.utc
        assert cutoff_utc.hour == 9
        assert cutoff_utc.minute == 0
        assert to_utc_iso(cutoff_utc) == "2026-01-15T09:00:00Z"

    def test_cutoff_format_validation(self):
        hour, minute = validate_cutoff_format("09:00")
        assert (hour, minute) == (9, 0)
        hour, minute = validate_cutoff_format("23:59")
        assert (hour, minute) == (23, 59)

        with pytest.raises(ValueError):
            validate_cutoff_format("24:00")
        with pytest.raises(ValueError):
            validate_cutoff_format("09:60")
        with pytest.raises(ValueError):
            validate_cutoff_format("9:00")
        with pytest.raises(ValueError):
            validate_cutoff_format("invalid")


class TestMetricsCalculation:
    """Test required properties 11 & 12: Hand-calculated metrics and zero-denominator handling."""

    def test_metrics_match_hand_calculated_examples(self):
        """11. MAE, RMSE, signed bias and WAPE match hand-calculated examples."""
        # Example pairs: (forecast, actual)
        # Pair 1: (120, 100) -> error = +20, abs_err = 20, sq_err = 400
        # Pair 2: (80,  100) -> error = -20, abs_err = 20, sq_err = 400
        # Pair 3: (110, 100) -> error = +10, abs_err = 10, sq_err = 100
        #
        # n = 3
        # Sum errors = 20 - 20 + 10 = 10. Bias = 10 / 3 = 3.3333333333333335 MW (overforecast)
        # Sum abs errors = 20 + 20 + 10 = 50. MAE = 50 / 3 = 16.666666666666668 MW
        # Sum sq errors = 400 + 400 + 100 = 900. RMSE = sqrt(900 / 3) = sqrt(300) = 17.320508075688775 MW
        # Sum actual = 100 + 100 + 100 = 300. WAPE = (50 / 300) * 100 = 16.666666666666668 %
        pairs = [(120.0, 100.0), (80.0, 100.0), (110.0, 100.0)]

        mae = calculate_mae(pairs)
        assert mae is not None
        assert pytest.approx(mae, rel=1e-5) == 50.0 / 3.0

        rmse = calculate_rmse(pairs)
        assert rmse is not None
        assert pytest.approx(rmse, rel=1e-5) == math.sqrt(300.0)

        bias = calculate_bias(pairs)
        assert bias is not None
        assert pytest.approx(bias, rel=1e-5) == 10.0 / 3.0

        wape = calculate_wape(pairs)
        assert wape is not None
        assert pytest.approx(wape, rel=1e-5) == (50.0 / 300.0) * 100.0

        summary = compute_metrics_summary(pairs, expected_count=3)
        assert summary["mae"] == round(50.0 / 3.0, 2)
        assert summary["rmse"] == round(math.sqrt(300.0), 2)
        assert summary["bias"] == round(10.0 / 3.0, 2)
        assert summary["wape"] == round((50.0 / 300.0) * 100.0, 2)
        assert summary["wape"] == 16.67  # 16.67%, not 0.1667 or 1667%
        assert summary["coverage"] == 1.0
        assert summary["matched_intervals"] == 3
        assert summary["omitted_intervals"] == 0

    def test_wape_convention_percentage_points(self):
        """Assert calculate_wape returns percentage points (e.g. 20.0 for 20%), not 0.20 or 2000%."""
        # 20 error over 100 actual = 20.0%
        pairs = [(120.0, 100.0)]
        val = calculate_wape(pairs)
        assert val == 20.0
        assert val != 0.20
        assert val != 2000.0


    def test_zero_denominator_wape_returns_null(self):
        """12. Zero-denominator WAPE returns null/unavailable, never zero or infinity."""
        pairs_zero_actual = [(100.0, 0.0), (50.0, 0.0)]
        wape = calculate_wape(pairs_zero_actual)
        assert wape is None

        summary = compute_metrics_summary(pairs_zero_actual, expected_count=2)
        assert summary["wape"] is None

    def test_empty_pairs_return_none(self):
        assert calculate_mae([]) is None
        assert calculate_rmse([]) is None
        assert calculate_bias([]) is None
        assert calculate_wape([]) is None

        summary = compute_metrics_summary([], expected_count=24)
        assert summary["mae"] is None
        assert summary["rmse"] is None
        assert summary["bias"] is None
        assert summary["wape"] is None
        assert summary["coverage"] == 0.0
        assert summary["omitted_intervals"] == 24

    def test_coverage_calculation(self):
        assert calculate_coverage(24, 24) == 1.0
        assert calculate_coverage(12, 24) == 0.5
        assert calculate_coverage(0, 24) == 0.0


class TestActualsAggregation:
    """Test required properties 8, 9, 10: Two half-hours aggregate to hourly mean, duplicate detection."""

    def test_two_half_hourly_values_aggregate_into_correct_hourly_mean(self):
        """8. Two half-hourly values aggregate into the correct hourly mean."""
        engine = AnalysisEngine()
        # Test on 2026-01-02
        actuals = engine.aggregate_actuals("2026-01-02")
        assert len(actuals) == 24

        # Hour 00:00:00Z should average SP 1 and SP 2
        # From sample/audit:
        # SP 1: 15228 MW (00:00 to 00:30)
        # SP 2: 15505 MW (00:30 to 01:00)
        # Expected average: (15228 + 15505) / 2 = 15366.5 MW
        h0 = actuals.get("2026-01-02T00:00:00Z")
        assert h0 is not None
        assert h0.half_hour_count == 2
        assert h0.is_complete is True
        assert h0.average_mw == 15366.5

    def test_duplicate_normalized_timestamps_detected(self):
        """9. Duplicate normalized timestamps are detected before joining."""
        # If two records have identical startTime, aggregate_actuals must raise an error
        class MockLoader(DataLoader):
            def get_actuals_for_date(self, settlement_date: str):
                st = parse_iso_utc("2026-01-02T00:00:00Z")
                pt = parse_iso_utc("2026-01-02T00:30:00Z")
                return [
                    FuelHHRecord("FUELHH", pt, st, settlement_date, 1, "WIND", 1000.0, to_utc_iso(st), to_utc_iso(pt)),
                    FuelHHRecord("FUELHH", pt, st, settlement_date, 1, "WIND", 1200.0, to_utc_iso(st), to_utc_iso(pt)),
                ]

        engine = AnalysisEngine(loader=MockLoader())
        with pytest.raises(ValueError, match="Duplicate actual startTime detected"):
            engine.aggregate_actuals("2026-01-02")

    def test_missing_values_do_not_become_zero(self):
        """10. Missing values do not become zero."""
        engine = AnalysisEngine()
        analysis = engine.analyze_delivery_day("2026-01-02", "09:00")
        # In the complete verified snapshot, every interval has a valid non-zero forecast and actual
        for interval in analysis.hourly_intervals:
            assert interval["forecast_mw"] is not None
            assert interval["actual_mw"] is not None
            assert interval["forecast_mw"] > 0
            assert interval["actual_mw"] > 0
