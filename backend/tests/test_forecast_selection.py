"""Tests for forecast vintage selection, cutoff enforcement, and incompleteness handling."""

from datetime import date, datetime, timezone

import pytest

from backend.app.config import DECISION_DATE_START, DELIVERY_DATE_START
from backend.app.engine import AnalysisEngine
from backend.app.loader import DataLoader, WindforRecord
from backend.app.timestamps import (
    make_cutoff_datetime,
    parse_date_str,
    parse_iso_utc,
    to_utc_iso,
)


class TestForecastSelection:
    """Forecast selection, cutoff compliance, and vintage evaluation tests."""

    def test_forecast_published_after_cutoff_is_excluded(self):
        """A forecast published after the cutoff is strictly excluded."""
        engine = AnalysisEngine()
        # Decision date 2026-01-01, Delivery date 2026-01-02
        decision_d = date(2026, 1, 1)
        delivery_d = date(2026, 1, 2)

        # Cutoff at 09:00 UTC (09:00 Europe/London)
        cutoff_utc = make_cutoff_datetime(decision_d, "09:00")
        vintages = engine.evaluate_vintages_for_delivery(decision_d, delivery_d, cutoff_utc)

        # On 2026-01-01, vintages were published at 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30
        # Vintages at 09:30, 11:30, 15:30, 18:30, 22:30 must be strictly excluded!
        publish_times = [v.publish_time_iso for v in vintages]

        assert "2026-01-01T09:30:00Z" not in publish_times
        assert "2026-01-01T11:30:00Z" not in publish_times
        assert "2026-01-01T15:30:00Z" not in publish_times
        assert "2026-01-01T18:30:00Z" not in publish_times
        assert "2026-01-01T22:30:00Z" not in publish_times

        for pt_iso in publish_times:
            pt_dt = parse_iso_utc(pt_iso)
            assert pt_dt <= cutoff_utc

    def test_latest_eligible_publication_is_selected_deterministically(self):
        """The latest eligible publication is selected deterministically."""
        engine = AnalysisEngine()

        # At default 09:00 cutoff, the latest eligible vintage for ALL 31 decision dates
        # must be the 07:30 UTC vintage of the decision date.
        for day_num in range(1, 32):
            decision_d = date(2026, 1, day_num)
            delivery_d = date(2026, 1, day_num + 1) if day_num < 31 else date(2026, 2, 1)

            analysis = engine.analyze_delivery_day(delivery_d.isoformat(), "09:00")
            assert analysis.status == "complete"
            assert analysis.selected_vintage is not None

            expected_pt = f"2026-01-{day_num:02d}T07:30:00Z"
            assert analysis.selected_vintage.publish_time_iso == expected_pt
            assert analysis.latest_complete_vintage is not None
            assert analysis.latest_complete_vintage.publish_time_iso == expected_pt

    def test_forecast_records_from_different_vintages_are_never_mixed(self):
        """Forecast records from different vintages are never mixed."""
        engine = AnalysisEngine()
        analysis = engine.analyze_delivery_day("2026-01-02", "09:00")

        selected_pt = analysis.selected_vintage.publish_time_iso
        # Verify that all 24 interval forecasts came from this exact single publish_time
        all_vintages = engine.loader.get_all_vintages()
        original_vintage_records = {
            r.start_time_iso: r.generation for r in all_vintages[selected_pt]
        }

        for interval in analysis.hourly_intervals:
            assert interval["publish_time"] == selected_pt
            assert interval["forecast_mw"] == original_vintage_records[interval["startTime"]]

    def test_incomplete_latest_vintage_reports_gaps_without_fallback(self):
        """Incomplete latest vintages report gaps and do not silently fall back or fabricate missing values."""
        # Scenario: Cutoff is set to 01:00 UTC on 2026-01-01.
        # On 2026-01-01, the first publication on that day was at 02:30 UTC (which is after 01:00).
        # The latest vintage published before 01:00 UTC was on 2025-12-31 at 22:30 UTC!
        # That vintage only covers delivery day 2026-01-02 up to 21:00 UTC (22 of 24 hours).
        # Hours 22:00Z and 23:00Z are missing.
        engine = AnalysisEngine()
        analysis = engine.analyze_delivery_day("2026-01-02", "01:00")

        # Must report status = "incomplete"
        assert analysis.status == "incomplete"
        assert analysis.selected_vintage is not None
        assert analysis.selected_vintage.publish_time_iso == "2025-12-31T22:30:00Z"
        assert analysis.selected_vintage.delivery_hours_count == 22
        assert analysis.selected_vintage.is_complete is False

        # Must NOT fall back to calling it complete
        assert analysis.latest_complete_vintage is None

        # Must report exact missing interval timestamps
        assert len(analysis.missing_intervals) == 2
        assert "2026-01-02T22:00:00Z" in analysis.missing_intervals
        assert "2026-01-02T23:00:00Z" in analysis.missing_intervals

        # Missing intervals in hourly_intervals list must have forecast_mw = None, NOT 0.0!
        h22 = next(i for i in analysis.hourly_intervals if i["startTime"] == "2026-01-02T22:00:00Z")
        assert h22["forecast_mw"] is None
        assert h22["signed_error_mw"] is None

        h23 = next(i for i in analysis.hourly_intervals if i["startTime"] == "2026-01-02T23:00:00Z")
        assert h23["forecast_mw"] is None
        assert h23["signed_error_mw"] is None

    def test_latest_complete_comparison_labelled_distinctly(self):
        """The optional latest-complete comparison is labelled distinctly."""
        # Using a custom synthetic loader where:
        # - Vintage A (05:00 UTC) has 24/24 hours (complete)
        # - Vintage B (08:00 UTC) has only 12/24 hours (incomplete)
        # At cutoff 08:30:
        # - Selected latest available must be Vintage B (08:00 UTC) with status 'incomplete'
        # - Latest complete vintage must be Vintage A (05:00 UTC)
        class IncompleteMockLoader(DataLoader):
            def get_actuals_for_date(self, settlement_date: str):
                return DataLoader.get_instance().get_actuals_for_date(settlement_date)

            def get_all_vintages(self):
                d_del = date(2026, 1, 2)
                st_hours = [f"2026-01-02T{h:02d}:00:00Z" for h in range(24)]

                # Vintage A: complete (24 hours)
                pt_a = parse_iso_utc("2026-01-01T05:00:00Z")
                v_a = [
                    WindforRecord("WINDFOR", pt_a, parse_iso_utc(h), 5000.0, h, to_utc_iso(pt_a))
                    for h in st_hours
                ]

                # Vintage B: incomplete (only first 12 hours)
                pt_b = parse_iso_utc("2026-01-01T08:00:00Z")
                v_b = [
                    WindforRecord("WINDFOR", pt_b, parse_iso_utc(h), 5500.0, h, to_utc_iso(pt_b))
                    for h in st_hours[:12]
                ]

                return {
                    to_utc_iso(pt_a): v_a,
                    to_utc_iso(pt_b): v_b,
                }

            def get_sorted_vintage_keys(self):
                return ["2026-01-01T05:00:00Z", "2026-01-01T08:00:00Z"]

        mock_engine = AnalysisEngine(loader=IncompleteMockLoader())
        analysis = mock_engine.analyze_delivery_day("2026-01-02", "08:30")

        # Primary latest available must be Vintage B
        assert analysis.selected_vintage.publish_time_iso == "2026-01-01T08:00:00Z"
        assert analysis.selected_vintage.is_complete is False
        assert analysis.status == "incomplete"

        # Distinct latest complete must be Vintage A
        assert analysis.latest_complete_vintage is not None
        assert analysis.latest_complete_vintage.publish_time_iso == "2026-01-01T05:00:00Z"
        assert analysis.latest_complete_vintage.is_complete is True

    def test_cutoff_variations_select_appropriate_vintages(self):
        """Testing cutoff sensitivity: earlier cutoffs select earlier vintages."""
        engine = AnalysisEngine()

        # At 08:00 cutoff -> 07:30 UTC vintage is selected
        a_08 = engine.analyze_delivery_day("2026-01-02", "08:00")
        assert a_08.selected_vintage.publish_time_iso == "2026-01-01T07:30:00Z"

        # At 05:00 cutoff -> 04:30 UTC vintage is selected
        a_05 = engine.analyze_delivery_day("2026-01-02", "05:00")
        assert a_05.selected_vintage.publish_time_iso == "2026-01-01T04:30:00Z"

        # At 03:00 cutoff -> 02:30 UTC vintage is selected
        a_03 = engine.analyze_delivery_day("2026-01-02", "03:00")
        assert a_03.selected_vintage.publish_time_iso == "2026-01-01T02:30:00Z"
