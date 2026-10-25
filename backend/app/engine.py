"""Analysis engine: forecast vintage selection, actuals aggregation, interval alignment, and metrics evaluation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.app.config import (
    DECISION_DATE_END,
    DECISION_DATE_START,
    DELIVERY_DATE_END,
    DELIVERY_DATE_START,
    EXPECTED_HOURLY_INTERVALS_PER_DAY,
    TOTAL_EXPECTED_HOURLY_INTERVALS,
)
from backend.app.loader import DataLoader, FuelHHRecord, WindforRecord
from backend.app.metrics import compute_metrics_summary
from backend.app.timestamps import (
    delivery_date_to_decision_date,
    is_valid_delivery_date,
    make_cutoff_datetime,
    parse_date_str,
    to_utc_iso,
    validate_cutoff_format,
)


@dataclass(frozen=True)
class AggregatedHourActual:
    hour_iso: str
    average_mw: float
    half_hour_count: int
    is_complete: bool  # True if 2 valid half-hours aggregated


@dataclass(frozen=True)
class VintageEvaluation:
    publish_time: datetime
    publish_time_iso: str
    records_count: int
    delivery_hours_count: int
    coverage_ratio: float
    is_complete: bool
    delivery_forecasts: dict[str, float]  # hour_iso -> forecast_mw


@dataclass
class DeliveryDayAnalysis:
    delivery_date: str
    decision_date: str
    cutoff_local: str
    cutoff_utc: str
    status: str  # 'complete', 'incomplete', 'unavailable'
    selected_vintage: VintageEvaluation | None
    latest_complete_vintage: VintageEvaluation | None
    hourly_intervals: list[dict[str, Any]]
    missing_intervals: list[str]
    matched_pairs: list[tuple[float, float]]  # (forecast, actual)
    metrics: dict[str, Any]


class AnalysisEngine:
    """Core analysis engine for Windline."""

    def __init__(self, loader: DataLoader | None = None) -> None:
        self.loader = loader or DataLoader.get_instance()
        # In-memory analysis cache keyed by cutoff_str
        self._analysis_cache: dict[str, dict[str, DeliveryDayAnalysis]] = {}

    def get_expected_hourly_timestamps(self, delivery_d: date) -> list[str]:
        """Generate the 24 standard UTC ISO timestamps for a delivery date (00:00 to 23:00)."""
        timestamps = []
        for h in range(24):
            dt = datetime(delivery_d.year, delivery_d.month, delivery_d.day, h, 0, 0, tzinfo=timezone.utc)
            timestamps.append(to_utc_iso(dt))
        return timestamps

    def aggregate_actuals(self, delivery_date_str: str) -> dict[str, AggregatedHourActual]:
        """Aggregate half-hourly actuals into clock-hour averages for a delivery date.
        
        Validates timestamps and prevents duplicate joins.
        Does NOT silently impute missing data.
        """
        records = self.loader.get_actuals_for_date(delivery_date_str)
        by_hour: dict[str, list[FuelHHRecord]] = defaultdict(list)
        seen_start_times: set[str] = set()

        for r in records:
            # Check for duplicate startTimes before grouping
            if r.start_time_iso in seen_start_times:
                raise ValueError(f"Duplicate actual startTime detected: {r.start_time_iso} on {delivery_date_str}")
            seen_start_times.add(r.start_time_iso)

            # Truncate to hour boundary
            hour_dt = r.start_time.replace(minute=0, second=0, microsecond=0)
            hour_iso = to_utc_iso(hour_dt)
            by_hour[hour_iso].append(r)

        aggregated: dict[str, AggregatedHourActual] = {}
        for hour_iso, hh_rows in by_hour.items():
            valid_gens = [row.generation for row in hh_rows if row.generation is not None]
            if not valid_gens:
                continue

            avg_mw = sum(valid_gens) / len(valid_gens)
            is_complete = (len(valid_gens) == 2)

            aggregated[hour_iso] = AggregatedHourActual(
                hour_iso=hour_iso,
                average_mw=avg_mw,
                half_hour_count=len(valid_gens),
                is_complete=is_complete,
            )

        return aggregated

    def evaluate_vintages_for_delivery(
        self,
        decision_date: date,
        delivery_date: date,
        cutoff_utc: datetime,
    ) -> list[VintageEvaluation]:
        """Find all eligible vintages (publishTime <= cutoff) and evaluate coverage for delivery date.
        
        Returns list of VintageEvaluation in descending order of publishTime (most recent first).
        """
        all_vintages = self.loader.get_all_vintages()
        sorted_keys = self.loader.get_sorted_vintage_keys()
        expected_hours = set(self.get_expected_hourly_timestamps(delivery_date))

        evaluations: list[VintageEvaluation] = []

        # Iterate sorted keys in reverse (latest first)
        for pt_iso in reversed(sorted_keys):
            records = all_vintages[pt_iso]
            if not records:
                continue

            pt_dt = records[0].publish_time
            # Policy Rule: publishTime <= cutoff_utc
            if pt_dt > cutoff_utc:
                continue

            # Extract forecasts strictly on delivery date
            delivery_forecasts: dict[str, float] = {}
            for r in records:
                if r.start_time_iso in expected_hours:
                    delivery_forecasts[r.start_time_iso] = r.generation

            covered_count = len(delivery_forecasts)
            is_complete = (covered_count == EXPECTED_HOURLY_INTERVALS_PER_DAY)
            coverage_ratio = covered_count / EXPECTED_HOURLY_INTERVALS_PER_DAY

            evaluations.append(
                VintageEvaluation(
                    publish_time=pt_dt,
                    publish_time_iso=pt_iso,
                    records_count=len(records),
                    delivery_hours_count=covered_count,
                    coverage_ratio=coverage_ratio,
                    is_complete=is_complete,
                    delivery_forecasts=delivery_forecasts,
                )
            )

        return evaluations

    def analyze_delivery_day(
        self,
        delivery_date_str: str,
        cutoff_str: str = "09:00",
    ) -> DeliveryDayAnalysis:
        """Run complete analysis for a single delivery date under a given cutoff."""
        delivery_d = parse_date_str(delivery_date_str)
        if not is_valid_delivery_date(delivery_d):
            raise ValueError(f"Delivery date {delivery_date_str} is outside the target window ({DELIVERY_DATE_START} to {DELIVERY_DATE_END})")

        decision_d = delivery_date_to_decision_date(delivery_d)
        decision_str = decision_d.isoformat()
        cutoff_utc = make_cutoff_datetime(decision_d, cutoff_str)
        cutoff_utc_iso = to_utc_iso(cutoff_utc)

        # 1. Aggregate actuals
        actuals_by_hour = self.aggregate_actuals(delivery_date_str)

        # 2. Evaluate eligible vintages
        vintages = self.evaluate_vintages_for_delivery(decision_d, delivery_d, cutoff_utc)

        # 3. Forecast selection policy:
        # - Primary: latest eligible vintage with forecast records for delivery date
        # - Optional comparison: latest complete eligible vintage
        selected_latest: VintageEvaluation | None = None
        latest_complete: VintageEvaluation | None = None

        for v in vintages:
            # Check latest available with records for this delivery date
            if selected_latest is None and v.delivery_hours_count > 0:
                selected_latest = v
            # Check latest complete
            if latest_complete is None and v.is_complete:
                latest_complete = v

        if selected_latest is None:
            status = "unavailable"
        elif selected_latest.is_complete:
            status = "complete"
        else:
            status = "incomplete"

        # 4. Hourly Alignment
        expected_timestamps = self.get_expected_hourly_timestamps(delivery_d)
        hourly_intervals: list[dict[str, Any]] = []
        missing_intervals: list[str] = []
        matched_pairs: list[tuple[float, float]] = []

        forecast_map = selected_latest.delivery_forecasts if selected_latest else {}

        for hour_iso in expected_timestamps:
            forecast_mw = forecast_map.get(hour_iso)
            actual_hour = actuals_by_hour.get(hour_iso)
            actual_mw = actual_hour.average_mw if actual_hour else None
            hh_count = actual_hour.half_hour_count if actual_hour else 0

            signed_error = (forecast_mw - actual_mw) if (forecast_mw is not None and actual_mw is not None) else None
            abs_error = abs(signed_error) if signed_error is not None else None

            if forecast_mw is not None and actual_mw is not None:
                matched_pairs.append((forecast_mw, actual_mw))
            else:
                missing_intervals.append(hour_iso)

            hourly_intervals.append({
                "startTime": hour_iso,
                "forecast_mw": round(forecast_mw, 1) if forecast_mw is not None else None,
                "actual_mw": round(actual_mw, 1) if actual_mw is not None else None,
                "signed_error_mw": round(signed_error, 1) if signed_error is not None else None,
                "absolute_error_mw": round(abs_error, 1) if abs_error is not None else None,
                "publish_time": selected_latest.publish_time_iso if selected_latest else None,
                "cutoff_utc": cutoff_utc_iso,
                "actual_half_hour_count": hh_count,
            })

        # 5. Daily Metrics
        metrics = compute_metrics_summary(matched_pairs, EXPECTED_HOURLY_INTERVALS_PER_DAY)

        return DeliveryDayAnalysis(
            delivery_date=delivery_date_str,
            decision_date=decision_str,
            cutoff_local=cutoff_str,
            cutoff_utc=cutoff_utc_iso,
            status=status,
            selected_vintage=selected_latest,
            latest_complete_vintage=latest_complete,
            hourly_intervals=hourly_intervals,
            missing_intervals=missing_intervals,
            matched_pairs=matched_pairs,
            metrics=metrics,
        )

    def analyze_window(self, cutoff_str: str = "09:00") -> dict[str, DeliveryDayAnalysis]:
        """Analyze all 31 delivery days for a given cutoff with in-memory caching."""
        validate_cutoff_format(cutoff_str)

        if cutoff_str in self._analysis_cache:
            return self._analysis_cache[cutoff_str]

        results: dict[str, DeliveryDayAnalysis] = {}
        curr = DELIVERY_DATE_START
        while curr <= DELIVERY_DATE_END:
            d_str = curr.isoformat()
            results[d_str] = self.analyze_delivery_day(d_str, cutoff_str)
            curr += timedelta(days=1)

        self._analysis_cache[cutoff_str] = results
        return results

    def get_overview(self, cutoff_str: str = "09:00") -> dict[str, Any]:
        """Compute the full-month overview including overall metrics and daily summaries."""
        window_analyses = self.analyze_window(cutoff_str)

        all_matched_pairs: list[tuple[float, float]] = []
        daily_summaries = []
        auditable_days = 0

        for d_str, day_analysis in sorted(window_analyses.items()):
            all_matched_pairs.extend(day_analysis.matched_pairs)
            if day_analysis.status == "complete":
                auditable_days += 1

            summary = {
                "delivery_date": day_analysis.delivery_date,
                "decision_date": day_analysis.decision_date,
                "cutoff_local": day_analysis.cutoff_local,
                "cutoff_utc": day_analysis.cutoff_utc,
                "status": day_analysis.status,
                "selected_publish_time": (
                    day_analysis.selected_vintage.publish_time_iso
                    if day_analysis.selected_vintage
                    else None
                ),
                "latest_complete_publish_time": (
                    day_analysis.latest_complete_vintage.publish_time_iso
                    if day_analysis.latest_complete_vintage
                    else None
                ),
                "expected_intervals": EXPECTED_HOURLY_INTERVALS_PER_DAY,
                "observed_intervals": len(day_analysis.matched_pairs),
                "coverage": day_analysis.metrics["coverage"],
                "mae": day_analysis.metrics["mae"],
                "rmse": day_analysis.metrics["rmse"],
                "bias": day_analysis.metrics["bias"],
                "wape": day_analysis.metrics["wape"],
            }
            daily_summaries.append(summary)

        overall_metrics = compute_metrics_summary(all_matched_pairs, TOTAL_EXPECTED_HOURLY_INTERVALS)

        return {
            "cutoff_local": cutoff_str,
            "decision_window": {
                "start": DECISION_DATE_START.isoformat(),
                "end": DECISION_DATE_END.isoformat(),
            },
            "delivery_window": {
                "start": DELIVERY_DATE_START.isoformat(),
                "end": DELIVERY_DATE_END.isoformat(),
            },
            "total_delivery_days": len(daily_summaries),
            "auditable_days": auditable_days,
            "overall_metrics": overall_metrics,
            "daily_summaries": daily_summaries,
        }
