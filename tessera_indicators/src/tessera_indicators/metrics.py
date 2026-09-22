"""Metrics and bootstrap intervals for bounded continuous indicators."""

from __future__ import annotations

import math

import numpy as np


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | int]:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    valid = np.isfinite(actual) & np.isfinite(predicted)
    actual, predicted = actual[valid], predicted[valid]
    if not len(actual):
        raise ValueError("No finite target/prediction pairs available for metrics.")
    error = predicted - actual
    centered = actual - actual.mean()
    denominator = float(np.square(centered).sum())
    r2 = math.nan if denominator == 0 else float(1 - np.square(error).sum() / denominator)
    slope, intercept = (math.nan, math.nan) if len(actual) < 2 else np.polyfit(actual, predicted, 1)
    return {
        "count": int(len(actual)),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
        "bias": float(error.mean()),
        "r2": r2,
        "calibration_slope": float(slope),
        "calibration_intercept": float(intercept),
    }


def bootstrap_mae_interval(y_true: np.ndarray, y_pred: np.ndarray, draws: int = 500, seed: int = 42) -> tuple[float, float]:
    actual, predicted = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    valid = np.isfinite(actual) & np.isfinite(predicted)
    actual, predicted = actual[valid], predicted[valid]
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(draws):
        indices = rng.integers(0, len(actual), len(actual))
        estimates.append(np.abs(predicted[indices] - actual[indices]).mean())
    return tuple(float(value) for value in np.quantile(estimates, [0.025, 0.975]))
