"""Pydantic schemas and typed response models for Windline API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field("healthy", description="Application health status")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    timestamp_utc: str = Field(..., description="Current UTC timestamp")


class MetadataResponse(BaseModel):
    project: str
    version: str
    data_provider: str
    api_base_url: str
    date_windows: dict[str, Any]
    resolution: dict[str, Any]
    default_cutoff: str
    timezone: str
    selection_policy: dict[str, Any]
    units: dict[str, str]
    metrics_definitions: dict[str, str]
    provenance: dict[str, Any]


class HourlyIntervalComparison(BaseModel):
    startTime: str = Field(..., description="Normalized hourly interval start in UTC (ISO 8601 with Z)")
    forecast_mw: float | None = Field(None, description="Forecast generation in MW")
    actual_mw: float | None = Field(None, description="Aggregated actual generation in MW (mean of half-hours)")
    signed_error_mw: float | None = Field(None, description="Forecast minus actual in MW (positive = overforecast)")
    absolute_error_mw: float | None = Field(None, description="Absolute error in MW")
    publish_time: str | None = Field(None, description="Publication timestamp of the selected forecast vintage")
    cutoff_utc: str | None = Field(None, description="Applied decision cutoff in UTC")
    actual_half_hour_count: int = Field(0, description="Number of valid half-hourly readings aggregated (expected 2)")


class VintageInfo(BaseModel):
    publish_time: str = Field(..., description="Publication timestamp in UTC (ISO 8601 with Z)")
    total_intervals: int = Field(..., description="Total forecast intervals contained in this vintage (~73)")
    delivery_intervals_covered: int = Field(..., description="Number of hours covered for target delivery date (max 24)")
    coverage_ratio: float = Field(..., description="Delivery coverage ratio (0.0 to 1.0)")
    is_complete: bool = Field(..., description="True if covers all 24 delivery hours")
    is_selected_latest: bool = Field(..., description="True if chosen as primary latest-available forecast")
    is_latest_complete: bool = Field(..., description="True if chosen as latest complete eligible vintage")


class MetricsBlock(BaseModel):
    expected_intervals: int
    matched_intervals: int
    omitted_intervals: int
    coverage: float
    mae: float | None = Field(None, description="Mean Absolute Error in MW")
    rmse: float | None = Field(None, description="Root Mean Squared Error in MW")
    bias: float | None = Field(None, description="Signed Mean Error in MW (forecast - actual)")
    wape: float | None = Field(None, description="Weighted Absolute Percentage Error in %")


class DeliveryDaySummary(BaseModel):
    delivery_date: str = Field(..., description="Delivery date (YYYY-MM-DD)")
    decision_date: str = Field(..., description="Decision date (YYYY-MM-DD)")
    cutoff_local: str = Field(..., description="Configured decision cutoff in Europe/London (HH:MM)")
    cutoff_utc: str = Field(..., description="Decision cutoff normalized to UTC")
    status: str = Field(..., description="Delivery day status: 'complete', 'incomplete', or 'unavailable'")
    selected_publish_time: str | None = Field(None, description="Publish time of the primary selected vintage")
    latest_complete_publish_time: str | None = Field(None, description="Publish time of latest complete eligible vintage")
    expected_intervals: int = Field(24, description="Expected delivery intervals (24)")
    observed_intervals: int = Field(..., description="Matched intervals with both forecast and actual")
    coverage: float = Field(..., description="Coverage ratio (0.0 to 1.0)")
    mae: float | None = None
    rmse: float | None = None
    bias: float | None = None
    wape: float | None = None


class DeliveryDayDetailResponse(BaseModel):
    delivery_date: str
    decision_date: str
    cutoff_local: str
    cutoff_utc: str
    status: str
    selected_vintage: VintageInfo | None
    latest_complete_vintage: VintageInfo | None
    intervals: list[HourlyIntervalComparison]
    missing_intervals: list[str]
    metrics: MetricsBlock


class OverviewResponse(BaseModel):
    cutoff_local: str
    decision_window: dict[str, str]
    delivery_window: dict[str, str]
    total_delivery_days: int
    auditable_days: int
    overall_metrics: MetricsBlock
    daily_summaries: list[DeliveryDaySummary]


class DeliveriesListResponse(BaseModel):
    cutoff_local: str
    total_days: int
    deliveries: list[DeliveryDaySummary]


class VintagesAuditResponse(BaseModel):
    delivery_date: str
    decision_date: str
    cutoff_local: str
    cutoff_utc: str
    selected_latest_vintage: str | None
    latest_complete_vintage: str | None
    eligible_vintages: list[VintageInfo]
