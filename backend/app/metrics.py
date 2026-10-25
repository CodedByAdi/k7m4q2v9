"""Deterministic metrics calculation for wind forecast analysis.

Definitions:
- MAE (Mean Absolute Error): mean(|forecast - actual|) in MW
- RMSE (Root Mean Squared Error): sqrt(mean((forecast - actual)^2)) in MW
- Signed Bias: mean(forecast - actual) in MW. Positive = overforecast, negative = underforecast
- WAPE (Weighted Absolute Percentage Error): sum(|forecast - actual|) / sum(actual) * 100 (%)
  Returns None if sum(actual) == 0 (zero denominator), avoiding Infinity or NaN
- Coverage: matched_intervals / expected_intervals (ratio 0.0 to 1.0)
"""

from __future__ import annotations

import math
from typing import Any, Sequence


def calculate_mae(pairs: Sequence[tuple[float, float]]) -> float | None:
    """Calculate Mean Absolute Error (MAE) in MW.
    
    Pairs are (forecast_mw, actual_mw). Returns None if pairs is empty.
    """
    if not pairs:
        return None
    total_abs_err = sum(abs(f - a) for f, a in pairs)
    return total_abs_err / len(pairs)


def calculate_rmse(pairs: Sequence[tuple[float, float]]) -> float | None:
    """Calculate Root Mean Squared Error (RMSE) in MW.
    
    Pairs are (forecast_mw, actual_mw). Returns None if pairs is empty.
    """
    if not pairs:
        return None
    total_sq_err = sum((f - a) ** 2 for f, a in pairs)
    return math.sqrt(total_sq_err / len(pairs))


def calculate_bias(pairs: Sequence[tuple[float, float]]) -> float | None:
    """Calculate Signed Bias in MW: mean(forecast - actual).
    
    Positive bias indicates overforecast, negative bias indicates underforecast.
    Returns None if pairs is empty.
    """
    if not pairs:
        return None
    total_err = sum(f - a for f, a in pairs)
    return total_err / len(pairs)


def calculate_wape(pairs: Sequence[tuple[float, float]]) -> float | None:
    """Calculate Weighted Absolute Percentage Error (WAPE) in percent (%).
    
    Formula: (sum(|forecast - actual|) / sum(actual)) * 100.
    Returns None if pairs is empty or if sum(actual) is zero (undefined/zero denominator).
    Never returns infinity or NaN.
    """
    if not pairs:
        return None
    sum_actual = sum(a for _, a in pairs)
    if sum_actual <= 0.0:
        return None
    sum_abs_err = sum(abs(f - a) for f, a in pairs)
    return (sum_abs_err / sum_actual) * 100.0


def calculate_coverage(matched_count: int, expected_count: int) -> float:
    """Calculate interval coverage ratio (0.0 to 1.0)."""
    if expected_count <= 0:
        return 0.0
    return round(min(1.0, max(0.0, matched_count / expected_count)), 4)


def compute_metrics_summary(
    pairs: Sequence[tuple[float, float]],
    expected_count: int,
) -> dict[str, Any]:
    """Compute all evaluation metrics and data coverage for a given collection of (forecast, actual) pairs."""
    matched_count = len(pairs)
    omitted_count = max(0, expected_count - matched_count)
    coverage = calculate_coverage(matched_count, expected_count)

    mae = calculate_mae(pairs)
    rmse = calculate_rmse(pairs)
    bias = calculate_bias(pairs)
    wape = calculate_wape(pairs)

    return {
        "expected_intervals": expected_count,
        "matched_intervals": matched_count,
        "omitted_intervals": omitted_count,
        "coverage": coverage,
        "mae": round(mae, 2) if mae is not None else None,
        "rmse": round(rmse, 2) if rmse is not None else None,
        "bias": round(bias, 2) if bias is not None else None,
        "wape": round(wape, 2) if wape is not None else None,
    }
