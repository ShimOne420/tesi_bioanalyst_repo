"""Shared metric and display-unit helpers for BIOMAP native outputs."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np


PRECIPITATION_UNIT_LABEL = "mm/mese"
PRECIPITATION_AUDIT = {
    "precipitation_unit": "mm/month",
    "precipitation_unit_it": PRECIPITATION_UNIT_LABEL,
    "precipitation_conversion": "raw_m * 1000",
}


def convert_display_values(variable_name: str, values: np.ndarray) -> tuple[np.ndarray, str]:
    """Convert native model values to the display units used by exports and UI."""
    array = np.asarray(values, dtype=np.float32)
    if variable_name in {"t2m", "d2m", "stl1", "stl2"}:
        return array - 273.15, "°C"
    if variable_name == "tp":
        return array * 1000.0, PRECIPITATION_UNIT_LABEL
    return array, "native"


def is_ndvi_metric(group: str | None, variable: str | None) -> bool:
    return (group or "").casefold() == "vegetation" and (variable or "").casefold() == "ndvi"


def metric_valid_mask(
    predicted_values: np.ndarray,
    observed_values: np.ndarray,
    *,
    group: str | None = None,
    variable: str | None = None,
    eps: float = 1e-12,
) -> np.ndarray:
    """Return cells that should participate in metrics for this feature."""
    pred = np.asarray(predicted_values, dtype=np.float64)
    obs = np.asarray(observed_values, dtype=np.float64)
    mask = np.isfinite(pred) & np.isfinite(obs)
    if is_ndvi_metric(group, variable):
        mask &= np.abs(obs) > eps
    return mask


def continuous_metric_summary(
    predicted_values: np.ndarray,
    observed_values: np.ndarray,
    *,
    group: str | None = None,
    variable: str | None = None,
    eps: float = 1e-12,
) -> dict[str, Any]:
    """Compute continuous metrics with BIOMAP validity rules."""
    pred_all = np.asarray(predicted_values, dtype=np.float64)
    obs_all = np.asarray(observed_values, dtype=np.float64)
    mask = metric_valid_mask(pred_all, obs_all, group=group, variable=variable, eps=eps)
    pred = pred_all[mask]
    obs = obs_all[mask]
    valid_count = int(pred.size)
    if valid_count == 0:
        return {
            "cell_count": 0,
            "valid_cell_count": 0,
            "metric_cell_count": 0,
            "predicted_mean": math.nan,
            "observed_mean": math.nan,
            "mae": math.nan,
            "rmse": math.nan,
            "bias": math.nan,
            "correlation": math.nan,
            "predicted_min": math.nan,
            "predicted_max": math.nan,
            "observed_min": math.nan,
            "observed_max": math.nan,
            "wape_pct": math.nan,
            "smaape_pct": math.nan,
            "smape_pct": math.nan,
            "rmae_pct": math.nan,
            "cvrmse_pct": math.nan,
            "relative_mae_pct": math.nan,
        }

    diff = pred - obs
    abs_error = np.abs(diff)
    mae = float(np.mean(abs_error))
    rmse = float(np.sqrt(np.mean(np.square(diff))))
    corr = math.nan
    if valid_count > 1 and float(np.std(pred)) > 0.0 and float(np.std(obs)) > 0.0:
        corr = float(np.corrcoef(pred, obs)[0, 1])

    observed_abs_sum = float(np.sum(np.abs(obs)))
    observed_abs_mean = float(abs(np.mean(obs)))
    symmetric_denominator = np.abs(pred) + np.abs(obs)
    symmetric_values = np.zeros_like(abs_error, dtype=np.float64)
    symmetric_mask = symmetric_denominator > eps
    symmetric_values[symmetric_mask] = 200.0 * abs_error[symmetric_mask] / symmetric_denominator[symmetric_mask]
    smaape = float(np.mean(symmetric_values))

    return {
        "cell_count": valid_count,
        "valid_cell_count": valid_count,
        "metric_cell_count": valid_count,
        "predicted_mean": float(np.mean(pred)),
        "observed_mean": float(np.mean(obs)),
        "mae": mae,
        "rmse": rmse,
        "bias": float(np.mean(diff)),
        "correlation": corr,
        "predicted_min": float(np.min(pred)),
        "predicted_max": float(np.max(pred)),
        "observed_min": float(np.min(obs)),
        "observed_max": float(np.max(obs)),
        "wape_pct": math.nan if observed_abs_sum <= eps else float(np.sum(abs_error) / observed_abs_sum * 100.0),
        "smaape_pct": smaape,
        "smape_pct": smaape,
        "rmae_pct": math.nan if observed_abs_mean <= eps else float(mae / observed_abs_mean * 100.0),
        "cvrmse_pct": math.nan if observed_abs_mean <= eps else float(rmse / observed_abs_mean * 100.0),
        "relative_mae_pct": math.nan if observed_abs_mean <= eps else float(mae / observed_abs_mean * 100.0),
    }


def cell_metric_columns(
    predicted_values: np.ndarray,
    observed_values: np.ndarray,
    *,
    group: str | None = None,
    variable: str | None = None,
    eps: float = 1e-12,
) -> dict[str, np.ndarray | float]:
    """Build per-cell metric columns plus aggregate WAPE for a matrix export."""
    pred = np.asarray(predicted_values, dtype=np.float64)
    obs = np.asarray(observed_values, dtype=np.float64)
    valid = metric_valid_mask(pred, obs, group=group, variable=variable, eps=eps)
    abs_error = np.abs(pred - obs)
    observed_abs = np.abs(obs)

    ape = np.full(pred.shape, np.nan, dtype=np.float64)
    ape_mask = valid & (observed_abs > eps)
    ape[ape_mask] = abs_error[ape_mask] / observed_abs[ape_mask] * 100.0

    symmetric_denominator = np.abs(pred) + observed_abs
    smaape = np.full(pred.shape, np.nan, dtype=np.float64)
    symmetric_mask = valid & (symmetric_denominator > eps)
    smaape[symmetric_mask] = 200.0 * abs_error[symmetric_mask] / symmetric_denominator[symmetric_mask]
    zero_symmetric_mask = valid & (symmetric_denominator <= eps)
    smaape[zero_symmetric_mask] = 0.0

    observed_abs_sum = float(np.sum(observed_abs[valid]))
    observed_abs_mean = float(abs(np.mean(obs[valid]))) if np.any(valid) else math.nan
    wape_contribution = np.full(pred.shape, np.nan, dtype=np.float64)
    if observed_abs_sum > eps:
        wape_contribution[valid] = abs_error[valid] / observed_abs_sum * 100.0
        wape = float(np.nansum(wape_contribution))
    else:
        wape = math.nan
    if np.any(valid):
        rmse = float(np.sqrt(np.mean(np.square(pred[valid] - obs[valid]))))
        rmae = math.nan if observed_abs_mean <= eps else float(np.mean(abs_error[valid]) / observed_abs_mean * 100.0)
        cvrmse = math.nan if observed_abs_mean <= eps else float(rmse / observed_abs_mean * 100.0)
    else:
        rmae = math.nan
        cvrmse = math.nan

    return {
        "valid_observation": valid.astype(bool),
        "ape_pct": ape,
        "wape_pct": wape,
        "wape_contribution_pct": wape_contribution,
        "smaape_pct": smaape,
        "smape_pct": smaape,
        "rmae_pct": rmae,
        "cvrmse_pct": cvrmse,
    }


def safe_unit_token(unit: str) -> str:
    """Convert display units to column-safe tokens."""
    normalized = unit.replace("°", "").replace("/", "_per_").lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized or "native"


def feature_value_label(variable: str, unit: str) -> str:
    return f"{variable}_{safe_unit_token(unit)}"
