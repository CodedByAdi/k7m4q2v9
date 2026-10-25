"""FastAPI route handlers for Windline REST API."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status

from backend.app.config import (
    APP_DESCRIPTION,
    APP_NAME,
    DECISION_DATE_END,
    DECISION_DATE_START,
    DEFAULT_CUTOFF_STR,
    DELIVERY_DATE_END,
    DELIVERY_DATE_START,
    TOTAL_DECISION_DAYS,
    TOTAL_DELIVERY_DAYS,
    VERSION,
)
from backend.app.engine import AnalysisEngine
from backend.app.loader import DataLoader
from backend.app.models import (
    DeliveriesListResponse,
    DeliveryDayDetailResponse,
    DeliveryDaySummary,
    HealthResponse,
    HourlyIntervalComparison,
    MetadataResponse,
    MetricsBlock,
    OverviewResponse,
    VintageInfo,
    VintagesAuditResponse,
)
from backend.app.timestamps import (
    delivery_date_to_decision_date,
    is_valid_delivery_date,
    make_cutoff_datetime,
    parse_date_str,
    to_utc_iso,
    validate_cutoff_format,
)

router = APIRouter(prefix="/api", tags=["Windline"])

# Global engine instance (uses singleton DataLoader)
_engine = AnalysisEngine()


def _get_validated_cutoff(cutoff: str) -> str:
    """Validate cutoff parameter or raise HTTP 400."""
    try:
        validate_cutoff_format(cutoff)
        return cutoff.strip()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _get_validated_delivery_date(delivery_date: str):
    """Validate delivery_date format and window, raising HTTP 400 on error."""
    try:
        d = parse_date_str(delivery_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid delivery date format: '{delivery_date}'. Expected 'YYYY-MM-DD'",
        ) from exc

    if not is_valid_delivery_date(d):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Delivery date '{delivery_date}' is outside the January delivery window "
                f"({DELIVERY_DATE_START.isoformat()} to {DELIVERY_DATE_END.isoformat()})"
            ),
        )
    return d


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return application health status and version."""
    return HealthResponse(
        status="healthy",
        app_name=APP_NAME,
        version=VERSION,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/metadata", response_model=MetadataResponse)
def get_metadata() -> MetadataResponse:
    """Return data sources, date windows, selection policy, units, and snapshot provenance."""
    provenance = _engine.loader.get_provenance()
    validation = _engine.loader.get_validation_report()

    return MetadataResponse(
        project=APP_NAME,
        version=VERSION,
        data_provider="Elexon Insights Solution (BMRS)",
        api_base_url="https://data.elexon.co.uk/bmrs/api/v1",
        date_windows={
            "decision_date_start": DECISION_DATE_START.isoformat(),
            "decision_date_end": DECISION_DATE_END.isoformat(),
            "delivery_date_start": DELIVERY_DATE_START.isoformat(),
            "delivery_date_end": DELIVERY_DATE_END.isoformat(),
            "total_decision_days": TOTAL_DECISION_DAYS,
            "total_delivery_days": TOTAL_DELIVERY_DAYS,
        },
        resolution={
            "fuelhh_actuals": "30 minutes (half-hourly)",
            "windfor_forecasts": "60 minutes (hourly)",
            "analysis_series": "60 minutes (hourly average of actuals joined to hourly forecasts)",
        },
        default_cutoff=DEFAULT_CUTOFF_STR,
        timezone="Europe/London",
        selection_policy={
            "description": "Select the latest eligible WINDFOR vintage with publishTime <= cutoff containing forecast records for target delivery date D+1.",
            "rule": "publishTime <= cutoff_utc (no post-cutoff future information allowed)",
            "handling_incomplete": "Exposed with observed interval count and gap list; never silently rolled back or zero-filled",
            "alternative_vintage": "Latest complete eligible vintage also provided for comparison",
        },
        units={
            "generation": "MW",
            "mae": "MW",
            "rmse": "MW",
            "bias": "MW (positive = overforecast, negative = underforecast)",
            "wape": "% (sum(|error|) / sum(actual) * 100)",
            "coverage": "ratio (0.0 to 1.0)",
        },
        metrics_definitions={
            "mae": "Mean Absolute Error: mean(|forecast - actual|) in MW",
            "rmse": "Root Mean Squared Error: sqrt(mean((forecast - actual)^2)) in MW",
            "bias": "Signed Mean Error: mean(forecast - actual) in MW. Overforecast > 0, underforecast < 0",
            "wape": "Weighted Absolute Percentage Error: sum(|forecast - actual|) / sum(actual) * 100 (null if sum(actual) == 0)",
            "coverage": "matched_intervals / expected_intervals (ratio 0.0 to 1.0)",
        },
        provenance={
            "source_files": validation,
            "metadata_file": provenance,
            "licensing": {
                "licence_name": "BMRS Open Data Licence",
                "licence_url": "https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/",
                "attribution": "Contains BMRS data © Elexon Limited copyright and database right 2026.",
                "disclaimer": "Elexon Limited does not endorse, sponsor, or approve Windline or its analytical findings.",
            },
        },
    )


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    cutoff: str = Query(DEFAULT_CUTOFF_STR, description="Decision cutoff time in Europe/London (HH:MM)"),
) -> OverviewResponse:
    """Return window overview, overall accuracy metrics, and daily summaries."""
    valid_cutoff = _get_validated_cutoff(cutoff)
    data = _engine.get_overview(valid_cutoff)
    return OverviewResponse(**data)


@router.get("/deliveries", response_model=DeliveriesListResponse)
def list_deliveries(
    cutoff: str = Query(DEFAULT_CUTOFF_STR, description="Decision cutoff time in Europe/London (HH:MM)"),
) -> DeliveriesListResponse:
    """List all available delivery days and their per-day completeness/metrics."""
    valid_cutoff = _get_validated_cutoff(cutoff)
    overview = _engine.get_overview(valid_cutoff)
    return DeliveriesListResponse(
        cutoff_local=valid_cutoff,
        total_days=overview["total_delivery_days"],
        deliveries=[DeliveryDaySummary(**d) for d in overview["daily_summaries"]],
    )


@router.get("/deliveries/{delivery_date}", response_model=DeliveryDayDetailResponse)
def get_delivery_detail(
    delivery_date: str,
    cutoff: str = Query(DEFAULT_CUTOFF_STR, description="Decision cutoff time in Europe/London (HH:MM)"),
) -> DeliveryDayDetailResponse:
    """Return hourly forecast/actual values, error metrics, and metadata for a specific delivery date."""
    valid_cutoff = _get_validated_cutoff(cutoff)
    d = _get_validated_delivery_date(delivery_date)
    d_str = d.isoformat()

    analysis = _engine.analyze_delivery_day(d_str, valid_cutoff)

    # Format selected vintage
    selected_v_info = None
    if analysis.selected_vintage:
        selected_v_info = VintageInfo(
            publish_time=analysis.selected_vintage.publish_time_iso,
            total_intervals=analysis.selected_vintage.records_count,
            delivery_intervals_covered=analysis.selected_vintage.delivery_hours_count,
            coverage_ratio=analysis.selected_vintage.coverage_ratio,
            is_complete=analysis.selected_vintage.is_complete,
            is_selected_latest=True,
            is_latest_complete=(
                analysis.latest_complete_vintage is not None
                and analysis.latest_complete_vintage.publish_time_iso == analysis.selected_vintage.publish_time_iso
            ),
        )

    # Format latest complete vintage
    complete_v_info = None
    if analysis.latest_complete_vintage:
        complete_v_info = VintageInfo(
            publish_time=analysis.latest_complete_vintage.publish_time_iso,
            total_intervals=analysis.latest_complete_vintage.records_count,
            delivery_intervals_covered=analysis.latest_complete_vintage.delivery_hours_count,
            coverage_ratio=analysis.latest_complete_vintage.coverage_ratio,
            is_complete=True,
            is_selected_latest=(
                analysis.selected_vintage is not None
                and analysis.selected_vintage.publish_time_iso == analysis.latest_complete_vintage.publish_time_iso
            ),
            is_latest_complete=True,
        )

    intervals = [HourlyIntervalComparison(**i) for i in analysis.hourly_intervals]
    metrics = MetricsBlock(**analysis.metrics)

    return DeliveryDayDetailResponse(
        delivery_date=analysis.delivery_date,
        decision_date=analysis.decision_date,
        cutoff_local=analysis.cutoff_local,
        cutoff_utc=analysis.cutoff_utc,
        status=analysis.status,
        selected_vintage=selected_v_info,
        latest_complete_vintage=complete_v_info,
        intervals=intervals,
        missing_intervals=analysis.missing_intervals,
        metrics=metrics,
    )


@router.get("/deliveries/{delivery_date}/vintages", response_model=VintagesAuditResponse)
def get_delivery_vintages(
    delivery_date: str,
    cutoff: str = Query(DEFAULT_CUTOFF_STR, description="Decision cutoff time in Europe/London (HH:MM)"),
) -> VintagesAuditResponse:
    """Return all eligible forecast vintages and their delivery coverage for audit and comparison."""
    valid_cutoff = _get_validated_cutoff(cutoff)
    d = _get_validated_delivery_date(delivery_date)
    decision_d = delivery_date_to_decision_date(d)
    cutoff_utc = make_cutoff_datetime(decision_d, valid_cutoff)
    cutoff_utc_iso = to_utc_iso(cutoff_utc)

    evaluations = _engine.evaluate_vintages_for_delivery(decision_d, d, cutoff_utc)

    selected_pt = None
    complete_pt = None

    for v in evaluations:
        if selected_pt is None and v.delivery_hours_count > 0:
            selected_pt = v.publish_time_iso
        if complete_pt is None and v.is_complete:
            complete_pt = v.publish_time_iso

    vintages_info = []
    for v in evaluations:
        vintages_info.append(
            VintageInfo(
                publish_time=v.publish_time_iso,
                total_intervals=v.records_count,
                delivery_intervals_covered=v.delivery_hours_count,
                coverage_ratio=v.coverage_ratio,
                is_complete=v.is_complete,
                is_selected_latest=(v.publish_time_iso == selected_pt),
                is_latest_complete=(v.publish_time_iso == complete_pt),
            )
        )

    return VintagesAuditResponse(
        delivery_date=d.isoformat(),
        decision_date=decision_d.isoformat(),
        cutoff_local=valid_cutoff,
        cutoff_utc=cutoff_utc_iso,
        selected_latest_vintage=selected_pt,
        latest_complete_vintage=complete_pt,
        eligible_vintages=vintages_info,
    )


@router.get("/export.csv")
def export_csv(
    cutoff: str = Query(DEFAULT_CUTOFF_STR, description="Decision cutoff time in Europe/London (HH:MM)"),
) -> Response:
    """Export interval-level forecast accuracy analysis as CSV with proper headers and escaping."""
    valid_cutoff = _get_validated_cutoff(cutoff)
    window_analysis = _engine.analyze_window(valid_cutoff)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

    # Required headers
    headers = [
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
    writer.writerow(headers)

    for d_str in sorted(window_analysis.keys()):
        day_analysis = window_analysis[d_str]
        for interval in day_analysis.hourly_intervals:
            forecast_val = interval["forecast_mw"]
            actual_val = interval["actual_mw"]
            signed_err = interval["signed_error_mw"]
            abs_err = interval["absolute_error_mw"]

            writer.writerow([
                day_analysis.delivery_date,
                day_analysis.decision_date,
                interval["startTime"],
                f"{forecast_val:.1f}" if forecast_val is not None else "",
                f"{actual_val:.1f}" if actual_val is not None else "",
                f"{signed_err:.1f}" if signed_err is not None else "",
                f"{abs_err:.1f}" if abs_err is not None else "",
                interval["publish_time"] or "",
                day_analysis.cutoff_utc,
            ])

    filename = f"windline_analysis_cutoff_{valid_cutoff.replace(':', '')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
